import requests
import bleach
import geneweaverdb as gwdb


def to_jira(description=None, fullname=None, email=None, user_id=None, user_page=None):
    """
    Submits a new issue to jira.jax.org
    :param user_page:
    :param user_id:
    :param description: string, description of the issue
    :param fullname: string
    :param email: string
    :return:
    """

    headers = {'Origin': 'https://jira.jax.org', 'User-Agent': ''}

    get_url = 'https://jira.jax.org/rest/collectors/1.0/template/form' \
              '/2233f647?os_authType=none'

    response = requests.get(url=get_url, headers=headers)

    # get user name and ID to add to the form submission
    user_info = gwdb.get_user(user_id)

    # a foil for the SQL injecting sec team
    if user_id == '922125168' or (user_info.first_name == "GUEST" and user_info.last_name == "GUEST"):
        return {'message': 'This appears no other thing to me than a foul and pestilent congregation of vapors.'}

    user_name = ''
    if user_info:

        user_name = "{0} {1} ({2})".format(
            user_info.first_name, user_info.last_name, user_id)

    description = "{0}\n\n{1}\n\n{2}".format(description, user_page, user_name)

    post_url = 'https://jira.jax.org/rest/collectors/1.0/template/form/2233f647'

    post_data = {
        'description': bleach.clean(description),
        'screenshot': '',
        'pid': 10404,
        'alt_token': response.cookies['atlassian.xsrf.token'],
        'fullname': bleach.clean(fullname),
        'email': bleach.clean(email),
        'webInfo': ''
    }
    headers = {
        'Origin': 'https://jira.jax.org/',
        'User-Agent': '',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': 'jira.jax.org',
        'Referer': get_url,
        'X-Atlassian-Token': 'no-check'
    }

    post_response = requests.post(post_url, data=post_data, headers=headers,
                                  cookies=response.cookies)

    if post_response.status_code == 200:
        return {'message': 'Report successfully submitted. Thank you.'}
    else:
        return {'message': 'Oops! There was a problem submitting your report.'}
