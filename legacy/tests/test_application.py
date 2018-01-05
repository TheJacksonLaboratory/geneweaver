from __future__ import print_function
import unittest
import xmlrunner
import application
import geneweaverdb
import publication_generator


class HomeTestCase(unittest.TestCase):

    def setUp(self):
        # initialize logic for test method, is run before each test
        application.app.config['DEBUG'] = True
        application.app.config['TESTING'] = True
        self.app = application.app.test_client()

    def tearDown(self):
        # take down anything we've specifically created for each test method
        self.app = None

    def test_app_root(self):
        rv = self.app.get('/')
        # then expect a 200...
        assert '200 OK' in rv.status


class PublicationAssignment(unittest.TestCase):

    user_id = None
    group_id = None
    group_name = None
    group_id_other = None
    group_name_other = None
    email = "Testing.VonUser@name.me"
    first = "Testing"
    last = "Von User"

    def setUp(self):
        # Create a test user and test group if one does not already exist
        user = geneweaverdb.get_user_byemail(self.email)
        if not user:
            user = geneweaverdb.register_user(self.first, self.last, self.email, "P@ssW0rd1!")
        self.user_id = user.user_id

        groups = geneweaverdb.get_user_groups(self.user_id)
        if not groups:
            geneweaverdb.create_group("Testing Users Test Group", "Private", self.user_id)
            geneweaverdb.create_group("Another Test Group", "Private", self.user_id)
            groups = geneweaverdb.get_user_groups(self.user_id)
        self.group_id = groups[0]
        self.group_name = geneweaverdb.get_group_name(self.group_id)
        self.group_id_other = groups[1]
        self.group_name_other = geneweaverdb.get_group_name(self.group_id_other)

        # configure a connection to the application
        application.app.config['DEBUG'] = True
        application.app.config['TESTING'] = True
        self.app = application.app.test_client()

    def tearDown(self):
        # Remove user/group relationship
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
        # Remove user/other group relationship
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''
                DELETE FROM production.usr2grp
                WHERE grp_id = (SELECT grp_id
                                FROM production.usr2grp
                                WHERE grp_id = %s AND  usr_id = %s AND u2g_privileges = 1)
                RETURNING grp_id;
            ''',
                (self.group_id_other, self.user_id,)
            )
            cursor.connection.commit()
        # Remove test group
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''
                DELETE FROM production.grp
                WHERE grp_id = %s;
            ''',
                (self.group_id,)
            )
            cursor.connection.commit()
        # Remove test other group
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''
                DELETE FROM production.grp
                WHERE grp_id = %s;
            ''',
                (self.group_id_other,)
            )
            cursor.connection.commit()
        # Remove test user
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(
                '''DELETE FROM production.usr WHERE usr_id=%s;''', (self.user_id,)
            )
            cursor.connection.commit()
        self.app = None

    def test_render_assign_publication(self):
        # given a valid session with user_id
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user_id'] = self.user_id
                sess['_fresh'] = True
            # when we view the publication_assignment page
            rv = self.app.get('/publication_assignment')

            # then expect a 200...
            assert '200 OK' in rv.status
            # and the body should contain some specific text
            assert 'Single Publication Assignment' in rv.data
            assert 'Publication Generators' in rv.data
            assert 'Generated Publication Listing' in rv.data

    def test_add_generator(self):
        # given valid generator parameters
        gen_name = 'test generator'
        gen_qstring = 'addiction'
        gen_group = self.group_id
        # and a valid session with user_id
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user_id'] = self.user_id
                sess['_fresh'] = True
            # when we attempt to add a new generator
            rv = self.app.post('/add_generator',
                               data=dict(name=gen_name,
                                         querystring=gen_qstring,
                                         group_id=gen_group))
            # then expect a 200...
            assert '200 OK' in rv.status
            for element in rv.response:
                assert 'Generator successfully added to group' in element
                # There appears to be a second blank entry, so we'll break after assertion
                break

            # Do post test cleanup -  This is not in the teardown as data was created in this method
            generator_id = self._get_generator_id(gen_name, gen_qstring, self.group_id, self.user_id)
            generator = publication_generator.PublicationGenerator.get_generator_by_id(generator_id)
            publication_generator.delete_generator(generator)

    def test_add_generator_missing_name(self):
        # given empty name parameter
        gen_name = ''
        # and valid qstring and group
        gen_qstring = 'addiction'
        gen_group = self.group_id
        # and a valid session with user_id
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user_id'] = self.user_id
                sess['_fresh'] = True
            # when we attempt to add a new generator
            rv = self.app.post('/add_generator',
                               data=dict(name=gen_name,
                                         querystring=gen_qstring,
                                         group_id=gen_group))
            # then expect a response of 412...
            assert '412' in rv.status
            # and expect to see message that generator successfully added
            for element in rv.response:
                assert 'You must provide a generator name, query string and group id' in element
                # There appears to be a second blank entry, so we'll break after assertion
                break

    def test_update_generator(self):
        # given valid generator parameters
        gen_name = 'test generator'
        gen_qstring = 'addiction'
        gen_group = self.group_id
        # and a valid session with user_id
        with self.app as c:
            with c.session_transaction() as sess:
                sess['user_id'] = self.user_id
                sess['_fresh'] = True
            # and an existing generator
            rv = self.app.post('/add_generator',
                               data=dict(name=gen_name,
                                         querystring=gen_qstring,
                                         group_id=gen_group))

            # when we get the correct generator id
            generator_id = self._get_generator_id(gen_name, gen_qstring, self.group_id, self.user_id)

            # and set some new values
            gen_name_change = 'my test generator'
            gen_qstring_change = 'addiction[MeSH Terms]'
            gen_group_change = self.group_id_other
            # and call the update service
            rv = self.app.post('/update_generator',
                               data=dict(id=generator_id,
                                         name=gen_name_change,
                                         querystring=gen_qstring_change,
                                         group_id=gen_group_change))
            # then expect a 200...
            assert '200 OK' in rv.status
            for element in rv.response:
                assert 'Generator successfully updated' in element
                # There appears to be a second blank entry, so we'll break after assertion
                break

        # Do post test cleanup -  This is not in the teardown as data was created in this method
        generator = publication_generator.PublicationGenerator.get_generator_by_id(generator_id)
        publication_generator.delete_generator(generator)

    def _get_generator_id(self, gen_name, gen_qstring, group_id, user_id):
        """
        Support method to get a generator id
        :param gen_name: The name of the generator
        :param gen_qstring: The query string of the generator
        :param group_id: The group that owns the generator
        :param user_id: The user who created the generator
        :return: the unique generator id
        """
        generators = publication_generator.list_generators(user_id, [str(group_id)])
        generator_id = -1
        for generator in generators:
            if generator.name == gen_name and generator.grp_id == group_id and \
                            generator.usr_id == user_id and generator.querystring == gen_qstring:
                generator_id = generator.stubgenid
                break
        return generator_id


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='reports/test-application'))