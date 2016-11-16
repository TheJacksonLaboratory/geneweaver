import unittest
import geneweaverdb


class TestGroupTaskManagement(unittest.TestCase):
    user_id = None
    group_id = None
    group_name = None
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
            with geneweaverdb.PooledCursor() as cursor:
                cursor.execute(
                    '''DELETE FROM usr WHERE usr_id=%s;''', (self.user_id,)
                )
                cursor.connection.commit()

    def test_get_group_by_id(self):
        group = geneweaverdb.get_group_by_id(self.group_id)
        self.assertEqual(group.grp_name, self.group_name)


if __name__ == '__main__':
    unittest.main()
