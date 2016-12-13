import unittest
import geneweaverdb


class TestGroupTaskManagement(unittest.TestCase):
    user_id = None
    group_id = None
    group_name = None
    geneset_id = None
    email = "Testing.VonUser@name.me"
    first = "Testing"
    last = "Von User"

    def setUp(self):
        """
        Create a test user and test group if one does not already exist
        :return: None
        """
        user = geneweaverdb.get_user_byemail(self.email)
        if not user:
            user = geneweaverdb.register_user(self.first, self.last, self.email, "P@ssW0rd1!")
        self.user_id = user.user_id

        groups = geneweaverdb.get_user_groups(self.user_id)
        if not groups:
            geneweaverdb.create_group("Testing Users Test Group", "Private", self.user_id)
            groups = geneweaverdb.get_user_groups(self.user_id)
        self.group_id = groups[0]
        self.group_name = geneweaverdb.get_group_name(self.group_id)

    def tearDown(self):
        """
        Remove test user and group we created
        :return: None
        """
        if self.group_name:
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
            if self.geneset_id:
                with geneweaverdb.PooledCursor() as cursor:
                    cursor.execute(
                        '''DELETE FROM production.geneset WHERE gs_id=%s;''', (self.geneset_id,)
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

    def test_get_server_side_grouptasks(self):
        """
        Test service for fetching tasks associated with a given group id
        :return:
        """
        # First create some tasks
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation,
                              gs_description, gs_count, gs_gene_id_type, gs_created, gs_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                           (self.user_id, 0, 'Testing Users Test GeneSet', 'TUTGS',
                            'A GeneSet for Testing Users Testing Purposes', 0, 0,
                            'normal',))
            gs_id = cursor.fetchone()[0]
            cursor.connection.commit()
            print 'Inserted gs_id: ' + str(gs_id)
            self.geneset_id = gs_id

        self.assertEqual(False, True)

if __name__ == '__main__':
    unittest.main()
