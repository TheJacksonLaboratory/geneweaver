"""
Tool Class Definition for Boolean Algebra. See service.py for the heavy lifting.
"""

import json

from tools.TOOLBOX.CS_Boolean import service
from tools import toolbase
from tools.celeryapp import celery


class BooleanAlgebra(toolbase.GeneWeaverToolBase):
    # Name of the tool
    name = "tools.BooleanAlgebra.BooleanAlgebra"

    # === Styling Constants ===
    COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
              '#D93459', '#5E228B', '#698FC6']
    TT = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
          'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
          'Canis familiaris']
    BG = ['#fae4db', '#f9fac5', '#b5faf5', '#fae3e9', '#f5fee1', '#f4dfff', '#78c679', '#41b6c4', '#7bccc4',
          '#8c96c6', '#fc8d59']
    BORDERS = ['#eeb44f', '#d7c000', '#44fcf7', '#fca5b7', '#8fcb0a', '#b4d1fb', '#41ab5d', '#1d91c0',
               '#4eb3d3', '#8c6bb1', '#ef6548']
    # ===

    def __init__(self, *args, **kwargs):
        self.init("BooleanAlgebra")
        self.urlroot=''

    def get_args(self):
        relation = self._parameters['BooleanAlgebra_Relation'].lower()
        output_prefix = self._parameters["output_prefix"]   # {.el,.dot,.png}
        at_least = self._parameters['at_least']
        
        # Strip 'GS' from gsids arguments to get ode gene ids
        geneset_ids = [g[2:] for g in self._gsids]
        
        return relation, output_prefix, at_least, geneset_ids

    def mainexec(self):
        # Get parameters for tool run
        relation, output_prefix, at_least, geneset_ids = self.get_args()

        # Results we know on submission
        result_dict = {
            # ---Styling Constants
            # Tool Tip
            'tt': self.TT,
            # Box Colors
            'colors': self.COLORS,
            # Background Colors
            'bg': self.BG,
            # Border Colors
            'borders': self.BORDERS,
            # ---Submission Info
            # Minimum number of gene sets
            'at_least': at_least,
            # Relation name -> Union, Inter., or Except
            'type': relation.title(),
            # Number of genesets in the current run of the tool
            'numGS': len(geneset_ids),
        }

        # Species for tool results page
        all_species_short, all_species_full = service.get_all_geneweaver_species_for_boolean(self.db.cursor())
        # Species for tool run
        species_in_genesets = service.get_species_in_genesets(self.db.cursor(), geneset_ids)

        # Raw sql result
        homolog_data = service.get_homologs_for_geneset(self.db.cursor(), geneset_ids, species_ids=species_in_genesets)
        # Grouped result
        bool_results = service.group_homologs(homolog_data, species_in_genesets)

        # Geneset Ids returned in the query
        result_geneset_ids = list(set([item[4] for item in homolog_data]))

        # Add tool results to result dict
        result_dict.update({
            # Number of genesets in the current run of the tool
            'numGS': len(geneset_ids),
            # Number of species in the current run of the tool
            'numSpecies': len(species_in_genesets),
            # All species for the header
            'all_species': all_species_short,
            # Like all species, but full name
            'all_species_full': all_species_full,
            'gsids': result_geneset_ids,
            'bool_results': bool_results,
        })

        # Circles are only displayed if there are less than 10 genesets
        if 1 <= len(result_geneset_ids) <= 10:
            result_dict['groups'] = service.create_circle_code(bool_results)

        if relation != 'union':
            # In case of Intersect, create dictionary of only
            # elements in bool_results with > than intersect
            intersection_sizes = service.intersect(bool_results, at_least)
            result_dict['intersect_results'] = intersection_sizes

            if relation == 'except':
                # If except then perform union minus the union of the intersections.
                # For GS A, B, C = (A U B U C)-((A N B) U (A N C) U (B N C))
                result_dict['bool_except'] = service.bool_except(bool_results)

        # Cluster result genes based on shared and unique genes per species
        # This will be placed in a d3 graph on the site
        #
        # it will report:
        # A. the number of genes unique to each species
        # B. the number of genes/species/intersection
        # B. the number of genes per species
        result_dict['bool_cluster'] = service.cluster_genes(homolog_data, species_in_genesets)

        # Update the results of the tool
        self._results.update(result_dict)

        # dump the dictionary into a json file that will be read
        # by the template
        with open(output_prefix + '.json', 'w') as fp:
            json.dump(self._results, fp)


BooleanAlgebra = celery.register_task(BooleanAlgebra())
