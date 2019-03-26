import requests
import bleach


def to_jira(description=None, fullname=None, email=None):
    """
    Submits a new issue to jira.jax.org
    :param description: string, description of the issue
    :param fullname: string
    :param email: string
    :return:
    """

    headers = {'Origin': 'https://jira.jax.org', 'User-Agent': ''}

    get_url = 'https://jira.jax.org/rest/collectors/1.0/template/form' \
              '/2233f647?os_authType=none'

    response = requests.get(url=get_url, headers=headers)

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
