
geneset_html_id_prefix = "geneset_"


def selected_geneset_ids(form):
    """
    this function takes a submitted form and extracts IDs for
    all selected geneset checkboxes
    :param form:    flask form (as in flask.request.form)
    :return: the list of geneset IDs
    """
    prefix_len = len(geneset_html_id_prefix)
    return [
        id_with_prefix[prefix_len:]
        for id_with_prefix in form.iterkeys()
        if id_with_prefix.startswith(geneset_html_id_prefix)
    ]
