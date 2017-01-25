import unittest
from werkzeug.datastructures import MultiDict
import curation_assignments
import geneweaverdb
import pub_assignments


class GroupTasks(unittest.TestCase):
    """
    This test class represents basic unit tests against the geneweaverdb functionality for pulling back group tasks
    """
    geneset_id = None
    user_id = None
    group_id = None
    group_name = None
    group_id_other = None
    group_name_other = None
    email = "Testing.VonUser@name.me"
    first = "Testing"
    last = "Von User"

    def setUp(self):
        # Create a test user if one does not already exist
        user = geneweaverdb.get_user_byemail(self.email)
        if not user:
            user = geneweaverdb.register_user(self.first, self.last, self.email, "P@ssW0rd1!")
        self.user_id = user.user_id

        # Create a test group if one does not already exist
        groups = geneweaverdb.get_user_groups(self.user_id)
        if not groups:
            geneweaverdb.create_group("Testing Users Test Group", "Private", self.user_id)
            groups = geneweaverdb.get_user_groups(self.user_id)
        self.group_id = groups[0]
        self.group_name = geneweaverdb.get_group_name(self.group_id)

        # create a geneset task
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation,
                              gs_description, gs_count, gs_gene_id_type, gs_created, gs_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                           (self.user_id, 0, 'Testing Users Test GeneSet', 'TUTGS',
                            'A GeneSet for Testing Users Testing Purposes', 0, 0,
                            'normal',))
            gs_id = cursor.fetchone()[0]
            cursor.connection.commit()
            self.geneset_id = gs_id

        # Create a curation assignment for our geneset and group
        curation_assignments.submit_geneset_for_curation(self.geneset_id,
                                                         self.group_id,
                                                         "Assignement made in test setup",
                                                         False)

    def tearDown(self):
        """
        Remove test user and group we created
        :return: None
        """
        # Cleanup after ourselves

        # It appears some notifications get fired, so we need to clean this up as well
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''DELETE from production.notifications where usr_id = %s''',
                           (self.user_id,))
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "DELETE FROM production.curation_assignments WHERE gs_id=%s", (self.geneset_id,))

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''DELETE FROM production.geneset WHERE gs_id=%s;''', (self.geneset_id,)
            )
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                "DELETE FROM production.geneset where usr_id=%s;", (self.user_id,)
            )
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''
            DELETE FROM production.usr2grp
            WHERE grp_id = (SELECT grp_id
                            FROM production.usr2grp
                            WHERE grp_id = %s AND  usr_id = %s AND u2g_privileges = 1)
            RETURNING grp_id;
            ''',
                (self.group_id, self.user_id,)
            )
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''
            DELETE FROM production.grp
            WHERE grp_id = %s;
            ''',
                (self.group_id,)
            )
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''DELETE FROM production.usr WHERE usr_id=%s;''', (self.user_id,)
            )
            cursor.connection.commit()

    def test_get_group_by_id(self):
        group = geneweaverdb.get_group_by_id(self.group_id)
        self.assertEqual(group.grp_name, self.group_name)

    def test_basic_get_grouptasks(self):
        # Given a group with a geneset assigned to it for curation w/ no notification
        curation_assignment_id = curation_assignments.get_geneset_curation_assignment(self.geneset_id)
        assert curation_assignment_id.gs_id == self.geneset_id
        # When we fetch tasks for a given group
        arguments = MultiDict([('group_id', self.group_id),
                               # Variables below are all datatable related and used within the server method...
                               ('sEcho', 1),
                               ('start', 0),
                               ('length', 10),
                               ('search[value]',''),
                               ('order[0][column]', 0),
                               ('order[0][dir]', 'asc')])
        results = geneweaverdb.get_server_side_grouptasks(arguments)
        # Then results should contain the geneset of interest
        data = results['aaData']
        assert data
        self.assertEqual(self.geneset_id, data[0][1])

    def test_grouptasks_with_pubassign(self):
        # Given a valid pubmed id
        pubmed_id = '27988283'
        # and a resulting publication object in geneweaver
        publication = geneweaverdb.get_publication_by_pubmed(pubmed_id, create=True)
        # and a publication assignment to a group
        pub_assignments.queue_publication(publication.pub_id,
                                          self.group_id,
                                          "Pub Assignment made in group tasks test")
        publication_assignment = pub_assignments.get_publication_assignment_by_pub_id(publication.pub_id, self.group_id)
        # and publication assigned to a curator
        pub_assignments.assign_publication(publication_assignment.id,
                                           self.user_id,
                                           self.user_id,
                                           "Curation assignment made in test")
        # and there is a geneset assigned to the publication
        new_geneset_id = pub_assignments.create_geneset_stub_for_publication(publication_assignment.id,
                                                                             'GroupTasks Test Method Geneset',
                                                                             'GTMG',
                                                                             'This is a geneset stub created in a unit test',
                                                                             1)  # species id for mouse
        # When we fetch tasks for a given group
        arguments = MultiDict([('group_id', self.group_id),
                               # Variables below are all datatable related and used within the server method...
                               ('sEcho', 1),
                               ('start', 0),
                               ('length', 10),
                               ('search[value]', ''),
                               ('order[0][column]', 0),
                               ('order[0][dir]', 'asc')])
        results = geneweaverdb.get_server_side_grouptasks(arguments)
        # Then results should contain the geneset of interest
        data = results['aaData']
        assert data
        found_geneset = False
        found_publication = False
        for row in data:
            if row[1] == new_geneset_id:
                # Confirm that this geneset is associated with the pubmed id
                found_geneset = True
                self.assertEqual(row[7], pubmed_id)
                self.assertEqual(row[8], 0)
            elif row[2] == pubmed_id:
                # Confirm that this publication has an associated geneset
                found_publication = True
                self.assertEqual(row[7], None)
                self.assertEqual(row[8], 1)
        assert found_geneset
        assert found_publication


        # Now do cleanup of publication assignment information
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''DELETE FROM production.gs_to_pub_assignment WHERE gs_id = %s
                              and pub_assign_id = %s''',
                           (new_geneset_id, publication_assignment.id))
            cursor.connection.commit()

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''DELETE FROM production.geneset WHERE gs_id = %s''',
                           (new_geneset_id,))

        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''DELETE FROM production.pub_assignments WHERE id = %s''',
                           (publication_assignment.id,))
            cursor.connection.commit()

        # If the publication has other pub_assignments, don't delete it
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''SELECT * FROM production.pub_assignments WHERE pub_id = %s''',
                           (publication.pub_id,))
            other_pubs = list(geneweaverdb.dictify_cursor(cursor))
            if len(other_pubs) == 0:
                cursor.execute('''DELETE FROM production.publications WHERE pub_id = %s''',
                               (publication.pub_id,))
                cursor.connection.commit()


if __name__ == '__main__':
    unittest.main()
