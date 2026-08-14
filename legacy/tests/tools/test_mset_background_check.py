"""
Regression tests for the MSET "gene not in background" message (GWC-51 / G3-783).

MSETcpp aborts with the raw C++ stderr "list_N not subset of its background" when
a list contains a gene its background does not. MSET.check_list_in_background
pre-empts that with a message naming the offending genes.

QA asked for one more thing (GWC-51, 2026-08-14): the message must also tell the
user to contact the GeneWeaver team, because only an administrator can change a
gene set's curation tier -- without that, users assume it is theirs to fix.

MSET.py imports celery, numpy and the tool base at module load, and ends by
registering an instance as a celery task, so those are shimmed. The function under
test touches no instance state, but it is reached through that registered instance
because the module attribute is the instance, not the class.

Run from legacy/:  python -m unittest tests.tools.test_mset_background_check
"""
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock

_TOOLS_WORKER = os.path.join(os.path.dirname(__file__), '..', '..', 'tools-worker')


def _clear_foreign_tools_modules():
    """Drop any `tools` entries another test module left in sys.modules.

    tests/db/test_get_genesets_hom_ids.py shims `tools` and `tools.toolcommon` as
    MagicMocks so geneweaverdb imports cleanly. Whichever module unittest imports
    first wins, so in a combined run those mocks are already installed and
    `from tools.MSET import ...` resolves against a MagicMock and fails. Remove
    them for the duration of our import, then restore, so neither module depends
    on collection order.
    """
    saved = {k: v for k, v in sys.modules.items()
             if k == 'tools' or k.startswith('tools.')}
    for k in saved:
        del sys.modules[k]
    return saved


def _install_import_shims():
    """Make `import tools.MSET` succeed without celery, numpy, or a DB."""
    for name in ('numpy',):
        sys.modules.setdefault(name, MagicMock())

    celeryapp = types.ModuleType('tools.celeryapp')
    celeryapp.logger = MagicMock()
    celeryapp.celery = MagicMock()
    # @celery.task(...) must return the undecorated function, and MSET.py ends with
    # `MSET = celery.register_task(MSET())` -- keep that an identity so the module
    # attribute stays the tool instance rather than becoming a MagicMock.
    celeryapp.celery.task = lambda *a, **k: (lambda fn: fn)
    celeryapp.celery.register_task = lambda task: task
    sys.modules['tools.celeryapp'] = celeryapp

    toolbase = types.ModuleType('tools.toolbase')

    class _GeneWeaverToolBase:
        # MSET.__init__ calls self.init(...) and resolves paths under TOOL_DIR.
        TOOL_DIR = tempfile.gettempdir()

        def __init__(self, *a, **k):
            pass

        def init(self, *a, **k):
            pass

    toolbase.GeneWeaverToolBase = _GeneWeaverToolBase
    sys.modules['tools.toolbase'] = toolbase

    # MSET.py does `import tools.toolbase` then references it as an attribute of
    # the package. Seeding sys.modules alone does not bind that attribute -- normal
    # import machinery would -- so set it on the real `tools` package explicitly.
    import tools
    tools.toolbase = toolbase
    tools.celeryapp = celeryapp


_saved_tools_modules = _clear_foreign_tools_modules()
sys.path.insert(0, os.path.abspath(_TOOLS_WORKER))
_install_import_shims()
# Module-level MSET is the registered tool INSTANCE (see register_task shim),
# so this is already bound -- call it with the four real arguments.
from tools.MSET import MSET as _mset  # noqa: E402

check = _mset.check_list_in_background

# Put sys.modules back as we found it. `check` already holds a direct reference,
# so restoring the other module's mocks cannot affect these tests -- and it keeps
# us from breaking that module if it is imported after this one.
for _name, _mod in _saved_tools_modules.items():
    sys.modules[_name] = _mod
del _saved_tools_modules


class MsetBackgroundMessageTests(unittest.TestCase):
    def setUp(self):
        self.bg = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False)
        self.bg.write('AAA\nBBB\nCCC\n')
        self.bg.close()
        self.addCleanup(os.unlink, self.bg.name)

    def _msg(self, genes):
        return check(genes, self.bg.name, 407805, 'List 2')

    # --- no complaint when the list fits the background ---------------------
    def test_returns_none_when_all_genes_present(self):
        self.assertIsNone(self._msg(['AAA', 'BBB']))

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(self._msg([]))

    def test_returns_none_when_background_file_missing(self):
        """An absent background is an infra failure handled downstream, not this."""
        self.assertIsNone(check(['AAA'], '/nonexistent/bg.txt', 1, 'List 1'))

    # --- the message itself -------------------------------------------------
    def test_names_the_offending_genes_and_counts(self):
        msg = self._msg(['AAA', 'LINC01924', 'VCAN-AS1'])
        self.assertIn('List 2 (GS407805)', msg)
        self.assertIn('2 of its 3 genes', msg)
        self.assertIn('LINC01924', msg)
        self.assertIn('VCAN-AS1', msg)

    def test_directs_the_user_to_the_geneweaver_team(self):
        """GWC-51: only admins can change a gene set's tier, so the message must
        not leave the user thinking it is theirs to fix."""
        msg = self._msg(['LINC01924'])
        self.assertIn('contact the GeneWeaver team', msg)
        self.assertIn('administrator', msg)
        self.assertIn('not something you can correct yourself', msg)

    def test_truncates_long_gene_lists(self):
        missing = ['GENE{}'.format(i) for i in range(40)]
        msg = self._msg(missing)
        self.assertIn('(and 25 more)', msg)
        self.assertIn('GENE0', msg)
        self.assertNotIn('GENE39', msg)

    def test_does_not_leak_raw_cpp_stderr(self):
        msg = self._msg(['LINC01924'])
        self.assertNotIn('not subset of its background', msg)


if __name__ == '__main__':
    unittest.main()
