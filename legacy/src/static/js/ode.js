var ODE = {};
(function () {
    _ODE = this;
    this.readOnly = false;

    this.redirect = function (url) {
        window.location.href = url;
    };

    this.select_all = function (check, input_name, container) {
        list = $(':input[name="' + input_name + '"]', container);
        list.each(function () {
            this.checked = check;
        });
        return false;
    };

    this.toggle = function (selector, e) {
        $(selector).each(function () {
            $(this).toggle();
        });

        if (e) { // show the minus symbol if now expanded
            if (e.src.substr(-17) === "images/expand.png") {
                e.src = "images/contract.png";
            }
            else {
                e.src = "images/expand.png";
            }
        }
        return false;
    };

    this.toggle_enabled = function (selector, en, andclear) {
        $(selector).each(function () {
            this.disabled = !en;
            if (!en && andclear) this.value = '';
        });
        return false;
    };

    // used in the html_input object to ensure that only numeric input is inserted,
    // and that the first two characters ("0.") are never deleted
    this.checkDecimalInput = function (obj, e) {
        var e = e || window.event;
        var v = e.keyCode;
        var result = true;

        if (!(v < 65 || v >= 91 && v <= 105 || v >= 112 && v <= 145))
            result = false;

        // backspace of either of the first two characters
        if (v == 8 && obj.selectionStart <= 2)
            result = false;

        // trying to edit before the second character
        if (obj.selectionStart <= 1 && v >= 46)
            result = false;

        return result;
    };

    this.update_deprecated = function (project_id, gs_id) {
        var url = "index.php";
        var params = "ajax_req=analyze&cmd=fixdeprecated&pj_id=" + project_id + "&gs_id=" + gs_id;

        pdiv = $('#project_' + project_id + '_deprecated');
        if (pdiv && gs_id == 0)
            pdiv.hide();

        if ($('#' + project_id + "TABLE") == null) {
            $('#' + project_id + "ahref").after('<div id="' + project_id + 'TABLE"></div>');
        }
        $('#' + project_id + 'TABLE').load(url, params);
        return false;
    };

    this.help_init = function () {
        numhelps = 0;
        $('.content-help').each(function () {
            $(this).toggle();
            numhelps++;
        });
        if (numhelps == 0) $('content-meta-help').hide();
    };

    this.multi_action = function (inputsel) {
        var act = inputsel.options[ inputsel.selectedIndex ].value;
        inputsel.selectedIndex = 0;
        if (act == '') return;

        var gs_ids = '';
        var gs_count = 0;

        var gsets = $('#my_genesets :input[name="gs_id[]"]').each(
            function () {
                if (this.checked) {
                    if (gs_ids != "") gs_ids += ",";
                    gs_ids += this.value;

                    gs_count++;
                }
            });

        if (gs_count == 0) {
            return;
        }

        switch (act) {
            case 'del_checked':
                if (confirm('Are you sure you wish to delete these ' + gs_count + ' GeneSets?')) {
                    this.redirect('index.php?action=manage&cmd=listgenesets&dellist=' + gs_ids);
                }
                break;
            case 'batch_edit':
                this.redirect('index.php?action=manage&cmd=batcheditgeneset&gs_ids=' + gs_ids);
                break;
            case 'change_owner':
                new_email = prompt('Enter the email address of the user you want to give these ' + gs_count + ' GeneSets:');
                if (new_email) {
                    this.redirect('index.php?action=manage&cmd=listgenesets&change_owner=' + escape(new_email) + '&gs_ids=' + gs_ids);
                }
                break;
        }
    };

    this.save_pref = function (pref_var, value) {
        $.get('index.php', 'ajax_req=analyze&cmd=save_prefs&' + pref_var + '=' + value);
    };

    this.toggle_tool = function (tool, e) {
        imgicon = $(e).children('img');
        if (imgicon.attr('src').substr(-17) === "images/expand.png")
            imgicon.attr('src', "images/contract.png");
        else imgicon.attr('src', "images/expand.png");
        $('#tool_params-' + tool).toggle();
        return false;
    };

    this.copy_field = function (start, from_id) {
        var input = $(':input[name="' + start + '_' + from_id + '"]')[0];
        inps = $('#batch_editor :input');

        //TODO: doesn't work in IE
        if (input.options) {
            for (n = 0; n < inps.length; n++) {
                if (inps[n].name.indexOf(start) == 0) {
                    for (o in input.options)
                        inps[n].options[o].selected = input.options[o].selected;
                }
            }
        } else {
            var value = input.value;
            for (n = 0; n < inps.length; n++) {
                if (inps[n].name.indexOf(start) == 0) inps[n].value = value;
            }
        }
        return false;
    };

    this.update_multigroup = function (sel) {
        var gsel = $(sel).val() || [];
        if (gsel.length == 0 || $.inArray('-1', gsel) != -1) gsel = ['-1'];
        if ($.inArray('0', gsel) != -1) gsel = ['0'];
        $(sel).val(gsel);
        $('#gs_groups').val(gsel.join(","));
        return true;
    };

    this._add_to_project_complete = function (resp) {
        // <!-- OK ## -->
        // <!-- DUPE ## OF ## -->
        // <!-- ERROR -->
        end = resp.indexOf("-->");
        if (end == -1) alert("An Error occurred.  Please try again.");
        else {
            msg = resp.substring(resp.indexOf("<!--") + 5, end - 1);
            if (msg == "ERROR") {
                alert("An Error occurred. Please refresh the page and try again.");
            } else if (msg.substring(0, 5) == "DUPE ") {
                ndupe = parseInt(msg.substring(5, msg.indexOf(" OF ")));
                total = parseInt(msg.substring(msg.indexOf(" OF ") + 4));
                if (ndupe == total) {
                    alert("All " + total + " GeneSet(s) already exist in that Project.");
                } else {
                    sel_msg = "Successfully added " + (total - ndupe) + " GeneSet(s) to the Project '" + sel_project + "',\n";
                    sel_msg += "but " + ndupe + " GeneSet(s) were already in it.";
                    alert(sel_msg);
                    window.location = 'index.php?action=analyze&project=' + sel_project;
                }
            } else if (msg.substring(0, 3) == "OK ") {
                total = parseInt(msg.substring(3));
                alert("Successfully added " + total + " GeneSet(s) to Project '" + sel_project + "'.");
                window.location = 'index.php?action=analyze&project=' + sel_project;
            }
        }
    }

    // sel: either a select item or null (ignored)
    // container: container to grab checked gs_ids from
    // project_name: if not null, the project name to use
    this.add_to_project = function (sel, container, project_name, id) {
        var url = "index.php";
        var params = "ajax_req=analyze&cmd=addToProject&name=";
        var gs_ids = [];
        var gs_count = 0;
        var sel_message = "";
        if (!project_name) { // if project name not supplied, use select box
            project_name = sel.options[sel.selectedIndex].value;
        }
        if (project_name == -1) return false;

        // in the genesets page, there's a "Select All Results" checkbox;
        // if this is checked, we need to grab all the results from the server
        if ($('#selectAllResults') && $('#selectAllResults').attr('checked')) {
            gs_ids = $('#resultsList').data('gsids');
            gs_count = $('#resultsList').data('gscount');
        } else {
            if (id != null) {
                gs_ids.push(id);
            }
            else {
                $(':input[name="gs_id[]"]:checked', container).each(function () {
                    gs_ids.push(this.value);
                });
            }
            gs_count = gs_ids.length;
            gs_ids.join(',');
        }

        if (gs_count == 0) {
            alert("Please select GeneSet(s) to add first");
            if (sel) sel.selectedIndex = 0;
            return true;
        }

        if (project_name == -2) {
            var name = prompt("Enter a name for the new Project");
            if (name == null) {
                if (sel) sel.selectedIndex = 0;
                return true;
            }

            // create new project named 'name' with the form
            params += name + "&gs_ids=" + gs_ids;
            sel_message = gs_count + " GeneSets to new Project '" + name + "'";
            sel_project = name;
        } else {
            // add to project from form to
            params += project_name + "&gs_ids=" + gs_ids;
            sel_message = gs_count + " GeneSets to Project '" + project_name + "'";
            sel_project = project_name;
        }
        $.get(url, params, this._add_to_project_complete);
        if (sel) sel.selectedIndex = 0;
        return true;
    };

    this.ode_share_pj_id = 0;
    this.ode_share_group = '';
    this._share_project_complete = function (resp) {
        var sel = $('#projectShareAJAXDiv');

        htmltop = 'Share with: <select name="shareWithGroup" onchange="return ODE.share_project(' + ode_share_pj_id + ', this);">';
        htmltop += '<option value="-1">Private</option><optgroup label="Groups">';
        htmlbottom = '</optgroup></select><span id="shared_pj_saved" style="background-color: #ffff00; padding: 2px;">Saved!</span>';

        sel.html(htmltop + resp + htmlbottom);

        if (ode_share_group != "") {
            if (!$('#' + ode_share_pj_id + 'share').length)
                $('#' + ode_share_pj_id + 'ahref').append('<span id="' + ode_share_pj_id + 'share" style="font-size: small; font-weight: normal;"></span>');
            $('#' + ode_share_pj_id + 'share').html("(Shared With " + ode_share_group + ")");
        } else {
            $('#' + ode_share_pj_id + 'share').remove();
        }
        $('#shared_pj_saved').fadeOut(1500);
    }
    this.share_project = function (pj_id, sel, container) {
        if (container == undefined) container = 'listform';
        var grp_id = sel.options[ sel.selectedIndex ].value;
        var grp_name = grp_id == -1 ? "" : sel.options[ sel.selectedIndex ].text;
        var url = "index.php";
        var params = "ajax_req=analyze&cmd=shareWithGroup&pj_id=" + pj_id + "&grp_id=" + grp_id;
        ode_share_pj_id = pj_id;
        ode_share_group = grp_name;

        $.get(url, params, this._share_project_complete);
    };

    this.remove_ontology = function (gs_id, ont_id, noblacklist) {
        var url = "index.php";
        var params = "action=manage&cmd=updategenesetontologies&gs_id=" + gs_id + "&remove=" + ont_id;
        if (noblacklist) params += '&noblack=yes';
        $.get(url, params, function (resp) {
            $('#ont_' + ont_id).remove();
            $('#ontology_list').append(resp);
        });
        return false;
    };

    this.add_ontology = function (gs_id, ont_id) {
        var url = "index.php";
        var params = "action=manage&cmd=updategenesetontologies&gs_id=" + gs_id + "&add=" + ont_id;
        $.get(url, params, function (resp) {
            $('#ontology_adder').after(resp);
        });
        $('#add_ontology').val('');
        return false;
    };

    this.confirm_ontology = function (gs_id, ont_id) {
        var url = "index.php";
        var params = "action=manage&cmd=updategenesetontologies&gs_id=" + gs_id + "&add=" + ont_id;
        $.get(url, params, function (resp) {
            $('#ont_' + ont_id).replaceWith(resp);
        });
        return false;
    };

    this.upload = {
        manual_pub: function () {
            $('.pub_field').each(function () {
                $(this).show();
            });
            $('#manual_pub_link').hide();
            return false;
        },
        pastebox: function () {
            this.pastewin = window.open("pastebox.php", "ODE Upload: Pastebox", "menubar=no,width=430,height=360,toolbar=no");
            this.pastewin.pCallback = this.paste_callback;
            this.pastewin.focus();
            return false;
        },
        paste_callback: function (filename) {
            ht = '<input type="hidden" name="file" id="file" value="' + filename + '">';
            ht += '<input type="text" style="width: auto;" disabled="disabled" value="Using Pasted File" />';
            ht += '<input type="button" style="width: auto;" value="clear" onclick="$(\'#uploaderDiv\').html(\'<input type=file id=file name=file />\'); return false;" />';
            $('#uploaderDiv').html(ht);
            return false;
        },
        help: function (topic) {
            this.helpwin = window.open("docs/gsedit_popup.html#" + wh, "ODE Help: Edit/Upload GeneSet",
                "menubar=no,width=430,height=360,toolbar=no,scrollbars=yes");
            this.helpwin.focus();
            return false;
        },
        chk_groups: function (grps) {
            var glist = "";
            // TODO: check works in IE
            for (i = 0; i < grps.length; i++) {
                if (grps[i].selected) {
                    if (glist != "") glist += ',';
                    glist += grps[i].value;
                }
            }

            // if nothing is selected, make it private
            if (glist == "") glist = -1;

            $('#gs_groups').val(glist);
        },
        chk_avail: function (radioBtn) {
            if (radioBtn.value == "Group") {
                $('.groupsRow').each(function () {
                    $(this).show();
                });
            } else if (radioBtn.value == "Private") {
                $('#gs_groups').val('-1');
                $('.groupsRow').each(function () {
                    $(this).hide();
                });
            } else if (radioBtn.value == "Public") {
                $('#gs_groups').val('0');
                $('.groupsRow').each(function () {
                    $(this).hide();
                });
            }
        },
        validate: function () {
            // check required fields
            req = "";
            if ($('#gs_name').val() == '') req += "GeneSet Name is required.\n";
            if ($('#gs_abbreviation').val() == '') req += "GeneSet Abbreviation is required.\n";
            if ($('#gs_description').val() == '') req += "GeneSet Description is required.\n";
            if ($("#file").val() == "" && $("#file_text").val() == "") req += "Input File is required.\n";
            if ($('#sp_id').val() == '0') req += "Species is required.\n";
            if ($('#gs_gene_id_type').val() == '0') req += "Gene Identifiers is required.\n";
            if (req == "") return true;

            window.alert(req);
            return false;
        }
    };

    //////////////////
    this.analyze = {
        validate: function () {
            var have = 0;
            $(':input[name="projectIDList[]"]').each(function () {
                if (this.checked) have++;
            });
            if (have > 0) return true;
            $(':input[name="gs_id[]"]').each(function () {
                if (this.checked) have++;
            });
            if (have > 1) return true;
            alert('Please select at least one Project or two GeneSets.');
            return false;
        },
        toggle_project: function (project_id) {
            if ($('#' + project_id + "TABLE").length) {
                if ($('#' + project_id + "ICON")[0].src.substr(-17) === "images/expand.png") {
                    $('#' + project_id + "TABLE").show();
                    $('#' + project_id + "ICON")[0].src = "images/contract.png";
                } else {
                    $('#' + project_id + "TABLE").hide();
                    $('#' + project_id + "TABLE :input[name=\"gs_id[]\"]").disabled = true;
                    $('#' + project_id + "ICON")[0].src = "images/expand.png";
                }
            } else {
                // list needs loaded
                var url = "index.php";
                var params = "ajax_req=analyze&cmd=getgenesets&prjid=" + project_id;
                if (_ODE.readOnly) params += "&readonly=true";
                $('#' + project_id + "ahref").after('<div id="' + project_id + 'TABLE"><img src="images/spinner.gif" /> Loading ...</div>');
                curSel = project_id;

                $('#' + project_id + 'TABLE').load(url, params);
                $('#' + project_id + "ICON")[0].src = "images/contract.png";
            }
            return false;
        },
        check_project: function (selID, whatchanged) {
            var p_chk = $('#' + selID + "_chk")[0].checked;
            if (whatchanged && whatchanged.name == 'gs_id[]') {
                var chk = whatchanged.checked;
                if (chk == false) {
                    $('#' + selID + "_chk")[0].checked = false;
                } else {
                    not_all = 0;
                    $("#sel_" + selID + ' :input[name="gs_id[]"]').each(function () {
                        if (!this.checked) not_all++;
                    });
                    if (!not_all)
                        $('#' + selID + "_chk")[0].checked = true;
                }
            } else if ($("#sel_" + selID).length) {
                $("#sel_" + selID + ' :input[name="gs_id[]"]').each(function () {
                    this.checked = p_chk;
                });
            }
        },
        rename_project: function (project_id) {
            var url = "index.php";
            var newName = window.prompt("Rename Project to:");
            if (newName != "" && newName != null) {
                var params = "ajax_req=analyze&cmd=renameProject&prjid=" + project_id + "&to=" + newName;
                $.get(url, params);
            }
            return false;
        },
        delete_project: function (project_id, project_name) {
            if (confirm('Are you sure you wish to delete the entire Project "' + project_name + '"?')) {
                var url = "index.php";
                var params = "ajax_req=analyze&cmd=deleteProject&prjid=" + project_id;
                $('#' + project_id + "DEL").load(url, params);
            }
        },
        remove_from_project: function (project_id, project_name, gs_list, x) {
            var url = "index.php";
            var gs_ids = gs_list;
            if (gs_list !== null) {
                if (!confirm('Are you sure you wish to remove these ' + gs_list.length + ' GeneSet(s) from the Project "' + project_name + '"?'))
                    return false;
                if (gs_list instanceof Array) {
                    gs_ids = "";
                    for (i = 0; i < gs_list.length; i++) {
                        if (i != 0) gs_ids += ',';
                        gs_ids += gs_list[i];
                    }
                }
            }
            var params = "ajax_req=analyze&cmd=removeFromProject&prjid=" + project_id + "&gs_id=" + gs_ids;
            $('#' + project_id + "TABLE").load(url, params);
            return false;
        },
        remove_selected_from_project: function (project_id, project_name) {
            var gs_list = [];
            $('#' + project_id + 'TABLE :input[name="gs_id[]"]').each(function () {
                if (this.checked)
                    gs_list.push(this.value);
            });
            this.remove_from_project(project_id, project_name, gs_list);
        }
    };

    this.search = {
        MAX_SEARCH_TERMS: 3, // maxmimum number of search terms to allow

        // the timestamp for the active AJAX request for a geneset search; updated
        // every time a new search is performed so that the page only updates once
        last_timestamp: null,

        // the last search parameters successfully searched, updated each time
        // search is updated
        last_params: { },

        // keep a copy of the last AJAX search to be sent; in the event that a new
        // query is entered while a current AJAX request exists, we simply update
        // this active_params variable
        active_params: null,

        selectedTab: null, // currently selected filter sidebar tab

        // add a new search input field to searchForm
        // q: query to add to the query box, or null
        // searchFields: boolean array for the checkboxes below; probably null
        add_search_term: function (q, searchFields) {
            var count = $('#searchInputs li').length;
            // sanity-check, to ward off against people abusing query string loading
            if (count >= this.MAX_SEARCH_TERMS) return;

            // show remove fields for existing inputs
            if (count == 1) {
                $('#searchInputs img[title=Remove]').toggleClass('disabled');
            }

            // create a new cell and append to it
            var li = $('<li>');
            var v = (q) ? 'value="' + q + '"' : '';
            li.append('<input type="text" name="q[]" size=50 ' + v + '/>');

            // checkboxes below
            var div = $('<div class="searchFields"></div>');

            // first, need to add images because they float right (Firefox bug?)
            // disable remove link if this is the first input being added
            v = (count == 0) ? ' class="disabled"' : '';
            div.append(
                '<img src="images/search_add.png" title="Add Search Term" alt="Add Search Term" onclick="ODE.search.add_search_term()" />' +
                    '<img src="images/search_remove.png" title="Remove" alt="Remove"' +
                    v + 'onclick="ODE.search.remove_search_term(this)" />');

            // now, add the stuff aligned left
            div.append('<b>Search in:</b>');
            $(['GeneSets', 'Genes', 'Abstracts', 'Ontologies']).each(function (i, field) {
                var checked = (!searchFields || searchFields[i]) ? ' checked="true"' : '';
                div.append('<label><input type="checkbox" name="search' + field +
                    '[]"' + checked + ' /> ' + field + '</label>');
            });

            // put it in a table row, and add it to the document
            li.append(div);
            $('#searchInputs').append(li);

            // disable adding more search inputs, if necessary
            if (count == this.MAX_SEARCH_TERMS - 1) {
                $('#searchInputs img[title="Add Search Term"]').toggleClass('disabled');
            }
        },

        remove_search_term: function (source) {
            var count = $('#searchInputs li').length;
            if (count == 1) return; // error! can't remove if only one left

            $(source.parentNode.parentNode).remove();
            if (count == 2) { // disable remove link if only one is now left
                $('#searchInputs img[title=Remove]').toggleClass('disabled');
            } else if (count == this.MAX_SEARCH_TERMS) { // re-enable "Add Search Term" buttons
                $('#searchInputs img[title="Add Search Term"]').toggleClass('disabled');
            }
            return false;
        },

        // given a general filter (e) that has been clicked, update the filters in
        // the tree-based tabs
        update_general_filter: function (e) {
            // get the category for e
            var tab = e.parents(':eq(2)').attr('id'); // 'general###List'
            tab = tab.substring(7, tab.indexOf('List'));
            // get the associated checkbox
            var cb = $('#tab' + tab + 'Content > ul > li > label > input[value=' + e.val() + ']');
            cb.attr('checked', e.attr('checked'));
            if (cb.attr('indeterminate')) {
                cb.attr('indeterminate', false);
            }
            // update the rest of the filters
            this.update_filters_tree(cb, tab);

            ODE.search.search_genesets('filter'); // update results list with AJAX
        },

        // onclick handler for filter checkboxes from one of the tree-structured tabs
        // e: a jquery checkbox element
        // selectedTab: tab to base the update from; defaults to ODE.search.selectedTab
        update_filters_tree: function (e, selectedTab) {
            if (!selectedTab) selectedTab = ODE.search.selectedTab;

            var level = e.data('level');

            if (level != 2) { // has children
                this._update_filters_children(e.parent().next(), e.attr('checked'));
            }
            if (level != 0) { // has a parent
                this._update_filters_parents(e.parents(':eq(3)'));
            }

            this.update_filters(selectedTab); // update all the filters

            ODE.search.search_genesets('filter'); // update results list with AJAX
        },

        // recursive call to update child checkboxes
        // e: the ul item associated with a filter checkbox
        // checked: (true | false) whether children should be checked
        _update_filters_children: function (e, checked) {
            // iterate through all children in this node's associated ul element;
            // for each child, it's checkbox, then recursively call this function
            e.children().each(function (i, x) {
                x = $(x);
                // check/uncheck checkbox
                x.children().first().children().first().attr('checked', checked);
                // if x (a <li> element) has two child elements (a <label> and a <ul>),
                // then recursively apply this function
                if (x.children().length == 2) {
                    ODE.search._update_filters_children(x.children().last(), checked);
                }
            });
        },

        // e: the <li> item containing a checkbox and <ul>
        // isIndeterminate: true if we just set the node to indeterminate
        _update_filters_parents: function (e, isIndeterminate) {
            if (!isIndeterminate) {
                // get an array of checked values for every child:
                // either true, false, or "indeterminate"
                var checked = $.map(e.children().last().children(), function (x) {
                    x = $(x);
                    if (x.children().first().children().first().attr('indeterminate')) {
                        isIndeterminate = true;
                        return "indeterminate";
                    }
                    return x.children().first().children().first().attr('checked');
                });

                // if no child was indeterminate, check if all children are the same
                if (!isIndeterminate) {
                    var i = 1;
                    while (i < checked.length && checked[i] == checked[i - 1]) ++i;
                    if (i == checked.length) { // were they all the same?
                        checked = checked[0]; // true or false
                    } else {
                        isIndeterminate = true;
                    }
                }
            }

            // set the element's attributes accordingly
            if (isIndeterminate) {
                e.children().first().children().first().attr('indeterminate', true);
                e.children().first().children().first().attr('checked', true);
            } else {
                e.children().first().children().first().attr('indeterminate', false);
                e.children().first().children().first().attr('checked', checked);
            }

            // update parent checkbox, if any
            if (e.children().first().children().first().data('level') != 0) {
                ODE.search._update_filters_parents(e.parent().parent(), isIndeterminate);
            }
        },

        // after a filter checkbox is clicked, update *all* the filters, in every tab
        // e: a checkbox element
        // selectedTab: the current tab to update the other values from; determines
        //   the order of the attributes
        // filterGroups: if supplied, use the specified six-digit array (see below)
        //   to update all tabs
        update_filters: function (selectedTab, filterGroups) {
            // first, build an array (checkGroups) of all tier, species, and attribute
            // triples (from the checkboxes in the selected tab), each mapped to a
            // 6-digit number, and only recording those which have been selected
            switch (selectedTab) {
                case 'Tiers':
                    var t = 10000;
                    var s = 100;
                    var a = 1;
                    break;
                case 'Species':
                    var t = 100;
                    var s = 10000;
                    var a = 1;
                    break;
                case 'Attributions':
                    var t = 100;
                    var s = 1;
                    var a = 10000;
                    break;
            }

            if (!filterGroups) {
                filterGroups = this.get_filter_groups(selectedTab);
            } else { // update all tabs
                selectedTab = '';
            }

            // update other two "tree-type" tabs
            if (selectedTab != 'Tiers') {
                this._update_filters_tab('Tiers', filterGroups, t, s, a);
            }
            if (selectedTab != 'Species') {
                this._update_filters_tab('Species', filterGroups, s, t, a);
            }
            if (selectedTab != 'Attributions') {
                this._update_filters_tab('Attributions', filterGroups, a, t, s);
            }

            // update General Tab checkboxes
            this._update_filters_general($('#tabTiersContent > ul > li > label > input'),
                $('#generalTiersList :checkbox').filter(':enabled'));
            this._update_filters_general($('#tabSpeciesContent > ul > li > label > input'),
                $('#generalSpeciesList :checkbox'));
            this._update_filters_general($('#tabAttributionsContent > ul > li > label > input'),
                $('#generalAttributionsList :checkbox'));
        },

        // does a one-to-one copy of the check state of x to the check state of y,
        // where x and y are both checkbox sets returned by jQuery
        _update_filters_general: function (x, y) {
            for (var i = 0; i < x.length; ++i) {
                y[i].checked = x[i].checked;
                y[i].indeterminate = x[i].indeterminate;
            }
        },

        // update_filters() calls this function to update the filters on the other
        //   two tree-like tabs that aren't currently being displayed
        // tabName: name of the tab to change
        // filterGroups: array of triple-digit numbers that our tier, species, and
        //                attribute combinations map to
        // w0, w1, w2: weights for each of the three fields when converting to a
        //             number to check for in filterGroups
        _update_filters_tab: function (tabName, filterGroups, w0, w1, w2) {
            var level0;
            var level1; // current first- and second-level nodes
            var num_level1;
            var num_level2; // counter for the number of that level node
            // we've seen for the current upper-level node

            $('#tab' + tabName + 'Content :checkbox').each(function (i, e) {
                var level = e.getAttribute('data-level');
                if (level == 0) {
                    level0 = e; // reference current top level
                    level0.indeterminate = false;
                    num_level1 = 0;
                }
                else if (level == 1) {
                    level1 = e; // reference current second level
                    level1.indeterminate = false;
                    ++num_level1;
                    num_level2 = 0;
                } else {
                    // check/uncheck third-level checkbox depending on whether its
                    // converted entry is found in the filterGroups array
                    e.checked = ($.inArray(
                        (level0.value * w0 + level1.value * w1 + e.value * w2), filterGroups) != -1);

                    // figure out if the current first- and second-level checkboxes are indeterminate
                    // by checking if the previous check value differs from the current check value
                    if (num_level2 > 1 && !level1.indeterminate && level1.checked != e.checked) {
                        level0.checked = false;
                        level0.indeterminate = true;
                        level1.checked = false;
                        level1.indeterminate = true;
                    } else {
                        level1.checked = e.checked; // assume second-level check matches, for now
                    }

                    // check whether this makes the top level-element indeterminate
                    if (num_level1 > 1 && !level0.indeterminate && level0.checked != level1.checked) {
                        level0.checked = false;
                        level0.indeterminate = true;
                    } else {
                        level0.checked = level1.checked; // assume top-level matches, for now
                    }

                    ++num_level2;
                }
            });
        },

        update_filters_toggle_all: function () {
            // if any are checked, uncheck all; otherwise, check all
            var checkAll = ($('#generalTiersList :checkbox').filter(function () {
                return this.checked || this.indeterminate;
            }).length === 0);

            $('#generalTiersList :checkbox:enabled').attr('checked', checkAll);
            $('#generalSpeciesList :checkbox').attr('checked', checkAll);
            $('#generalAttributionsList :checkbox').attr('checked', checkAll);
            $('#tabTiersContent :checkbox').attr('checked', checkAll);
            $('#tabSpeciesContent :checkbox').attr('checked', checkAll);
            $('#tabAttributionsContent :checkbox').attr('checked', checkAll);

            $('#generalTiersList :checkbox:enabled').attr('indeterminate', false);
            $('#generalSpeciesList :checkbox').attr('indeterminate', false);
            $('#generalAttributionsList :checkbox').attr('indeterminate', false);
            $('#tabTiersContent :checkbox').attr('indeterminate', false);
            $('#tabSpeciesContent :checkbox').attr('indeterminate', false);
            $('#tabAttributionsContent :checkbox').attr('indeterminate', false);

            ODE.search.search_genesets('filter'); // update results list with AJAX
        },

        // returns an array of six-digit mappings of all selected tier, species, and
        // attribute triples (every two characters represents the integer value for
        // each tribute, respectively; the leading digit might be zero)
        // tabName: the tab to use to build the array
        get_filter_groups: function (tabName) {
            var filterGroups = [];
            // iterate through checkboxes in order
            $('#tab' + tabName + 'Content :checkbox').each(function (i, e) {
                var level = e.getAttribute('data-level');
                if (level == 0) level0 = e.value; // change current top level
                else if (level == 1) level1 = e.value; // change current second level
                else if (e.checked) { // add triple if this is checked
                    filterGroups.push(level0 * 10000 + level1 * 100 + e.value * 1); // save as integer
                }
            });

            return filterGroups;
        },

        // coming from page navigation; load stored query from history, if any, and
        // perform a search
        load_query: function () {
            // if a history exists, load the static bits
            // IE < 10 doesn't support history.state. Yay!
            if (history.state) {
                // set query
                var q = history.state['q[]'];
                if (q.length == 0) {
                    document.title = 'Search for GeneSets';
                } else {
                    var q_str = q.map(function (e) {
                        return "'" + e + "'";
                    }).join(' AND ');
                    document.title = "Search results for " + q_str;
                }

                // clear current search fields and replace them
                $('#searchInputs li').remove();
                for (i in q) {
                    ODE.search.add_search_term(q[i]);
                }

                // set search fields to checked if the history contains an entry for them
                $(['searchGeneSets[]', 'searchGenes[]', 'searchAbstracts[]', 'searchOntologies[]']).each(function (i, field) {
                    $(':checkbox[name="' + field + '"]').each(function (j, e) {
                        e.checked = history.state[field][j];
                    });
                });
                ODE.search.search_genesets('pageLoad', history.state); // pass in existing parameters
            } else { // from home/refresh/back/forward; query boxes already added
                // add an empty search field, if none exist
                if ($('#searchInputs li').length == 0) {
                    ODE.search.add_search_term();
                } else {
                    ODE.search.search_genesets('pageLoad');
                }
            }
        },

        // AJAX function that updates the genesets results list
        // requestType: {'form', 'updateSidebar', 'filter', 'page', 'sort'}
        // params: existing parameter set to use, if coming from a page load
        search_genesets: function (requestType, params) {
            // get query values as an array of strings
            var q = $.map($('#searchForm input[name="q[]"]'), function (e) {
                return $.trim(e.value);
            });

            // if no queries entered, do nothing
            //var query_count = q.filter(function(e) { return !!e; }).length;
            if ($(q).filter(function (i, e) {
                return !!e;
            }).length == 0) {
                return false;
            }

            // true if first call to this function
            var newQuery = $.isEmptyObject(this.last_params);

            // if this isn't the first call to this function, figure out if either the
            // search terms have changed or their associated fields have changed
            if (!newQuery && requestType == 'form') {
                var max_length = Math.max(q.length, this.last_params['q[]'].length);

                for (var i = 0; i < max_length && !newQuery; ++i) {
                    // if q[i] == '' and last_params['q[]'][i] is undefined, this evaluates to false
                    newQuery = ((q[i] || null) != this.last_params['q[]'][i]);

                    // if it evaluated to false, and there's something in the search box,
                    // check if any of the related fields changed
                    if (!newQuery && q[i]) {
                        newQuery = $($('#searchForm .searchFields')[i]).find(':checkbox').filter(function () {
                            return this.checked != ODE.search.last_params[this.name][i];
                        }).length > 0; // length > 0 if any of the fields are different
                    }
                }

                // if this isn't a new query, and the search form trigged the call, quit
                if (!newQuery) return false;

                // if a new query and the browser doesn't support history.state (lookin
                // at you IE...), redirect, instead
                if (newQuery && !history.pushState) {
                    window.location = 'index.php?action=search&cmd=newPage&' +
                        $('#searchForm form:first').serialize();
                    return false;
                }
            }

            // make a note that this is the new current AJAX query; other current AJAX
            // queries will not execute when they reach their callback
            var timestamp = new Date;
            this.last_timestamp = timestamp;

            document.body.style.cursor = 'wait'; // set cursor to busy

            // if coming from a page load or navigation, load search parameters from history
            if (params) {
                params.newQuery = false;
                params.updateSidebar = true;
            } else if (!newQuery) {
                // deep_copy: copy data from object x to object y
                var deep_copy = function (x, y) {
                    for (var p in x) { // for each element in x
                        // if it's an array or object, recursively deep copy it
                        if ($.isArray(x[p])) {
                            y[p] = [];
                            deep_copy(x[p], y[p]);
                        } else if ($.isPlainObject(x[p])) {
                            y[p] = {};
                            deep_copy(x[p], y[p]);
                        } else { // normal variable, just assign it
                            y[p] = x[p];
                        }
                    }
                }

                // if not a new query, perform a deep copy of existing parameters
                params = { };
                if (this.active_params) {
                    deep_copy(this.active_params, params);
                } else {
                    deep_copy(this.last_params, params);
                }

                // now, figure out what fired the event and update it
                switch (requestType) {
                    case 'page':
                        params.page = $('#page').val();
                        break;

                    case 'sort':
                        params.page = 1; // reset page
                        params.sort = $('#sort').val();
                        break;

                    case 'size':
                        params.page = 1; // reset page

                        params.size_low = $('span[name=size_low]').html();
                        params.size_high = $('span[name=size_high]').html();

                        params.updateSidebar = true; // need to update sidebar counts
                        break;

                    case 'updateSidebar':
                        params.page = 1; // reset page

                        // general check values
                        params.includeProvisional = $('#includeProvisional')[0].checked;
                        params.includeDeprecated = $('#includeDeprecated')[0].checked;
                        params.group = $('#group').val();

                        // indicate we should update the sidebar (to reflect changes in tier,
                        // species, and group counts)
                        params.updateSidebar = true;
                        break;

                    case 'filter':
                        params.page = 1; // reset page

                        // use the tiers tab to retrieve (tier, species, attribution) triples
                        // in six-digit integer form
                        params['filterGroups[]'] = this.get_filter_groups('Tiers');
                        break;
                }
            } else { // new query; set default search parameters
                params = {
                    action: 'search',
                    cmd: 'genesets',
                    'q[]': q, // current queries
                    newQuery: true
                };

                // save checkbox parameters from search fields
                $(['searchGeneSets[]', 'searchGenes[]', 'searchAbstracts[]', 'searchOntologies[]']).each(function (i, field) {
                    params[field] = [];
                    $(':checkbox[name="' + field + '"]').map(function () {
                        params[field].push(this.checked);
                    });
                });

                // note: filter values (tiers, etc.) will reset automatically

                // load existing sidebar values if the searchResultsDiv is not empty
                if (requestType !== 'pageLoad' && $('#resultList').attr('gscount') > 0) {
                    // general filter sidebar options
                    params.selectedTab = this.selectedTab;
                    params.includeProvisional = $('#includeProvisional')[0].checked;
                    params.includeDeprecated = $('#includeDeprecated')[0].checked;
                    params.group = $('#group').val();
                } else { // defaults
                    params.selectedTab = 'General';
                    params.includeProvisional = true;
                    params.includeDeprecated = false;
                    params.group = 0;
                }
            }

            this.active_params = params;

            // serialize parameters
            var params_string = [];
            var q_encoded = []; // our URL-encoded query string
            var q_title = []; // the new title for our page
            for (p in params) {
                if ($.isArray(params[p])) { // add each entry separately
                    for (i in params[p]) {
                        params_string.push(p + '=' + encodeURIComponent(params[p][i]));
                        // build query strings, but only for existing terms
                        if (p == 'q[]' && params[p][i]) {
                            q_encoded.push(params_string[params_string.length - 1]);
                            q_title.push("'" + params[p][i] + "'");
                        }
                    }
                } else {
                    params_string.push(p + '=' + encodeURIComponent(params[p]));
                }
            }

            // create our encoded query string
            q_encoded = (q_encoded.length > 0) ? '&' + q_encoded.join('&') : '';

            // make our page title
            if (q_title.length == 0) {
                q_title = 'Search for GeneSets';
            } else {
                q_title = 'Search Results for ' + q_title.join(' AND ');
            }

            // perform query ansynchronously
            $.get(
                'index.php',
                params_string.join('&'), // query string
                function (response) { // callback
                    // verify that no other AJAX queries have been called
                    if (ODE.search.last_timestamp != timestamp) {
                        return;
                    }

                    // update content of relevant elements
                    // if a new query, set page title and save the search in the history
                    if (params.newQuery || params.updateSidebar) {
                        // we're going to subsequently paste this back into the document
                        var searchForm = $('#searchForm');

                        $('#searchResultsDiv').html(response); // update results list and filter sidebar
                        // IE 8 workaround woo yay we love IE
                        if (!$('#searchResultsDiv').html()) {
                            $('#searchResultsDiv')[0].innerHTML = response;
                        }

                        // re-insert the search form
                        searchForm.attr('class', 'searchForm'); // turn off "onlyElement"
                        searchForm.insertAfter('#searchFilters');

                        // if any results, save the initial size range
                        params.size_low = parseInt($('span[name=size_low]').html());
                        params.size_high = parseInt($('span[name=size_high]').html());
                        $('#gs_size_slider').slider({
                            range: true,
                            min: parseInt($('#size_min').val()),
                            max: parseInt($('#size_max').val()),
                            step: 1,
                            values: [params.size_low, params.size_high],
                            slide: function (event, ui) {
                                $('span[name=size_low]').html(ui.values[0]);
                                $('span[name=size_high]').html(ui.values[1]);
                            },
                            start: function (event, ui) {
                                this.previous_low = ui.values[0];
                                this.previous_high = ui.values[1];
                            },
                            stop: function (event, ui) {
                                if (ui.values[0] != this.previous_low ||
                                    ui.values[1] != this.previous_high) {
                                    ODE.search.search_genesets('size');
                                }
                            }
                        });

                        if (params.newQuery) {
                            // save last successful search in search history
                            // but only do this if there was a last search
                            if (history.pushState && !$.isEmptyObject(ODE.search.last_params)) {
                                history.pushState(ODE.search.last_params, document.title);
                            }

                            // update page title
                            document.title = q_title;
                        }
                    } else { // neither a new query nor are we updating sidebar counts
                        $('#searchResults').html(response); // update results list only
                        // IE 8 workaround woo yay we love IE
                        if (!$('#searchResults').html()) {
                            $('#searchResults')[0].innerHTML = response;
                        }
                    }

                    // show/hide the top dropdowns if there are/aren't results listed
                    if ($('#genesetList tr[id^=GS]').length <= 0) {
                        $('.rightPanel').hide();
                    } else {
                        $('.rightPanel').show();
                    }

                    document.body.style.cursor = ''; // set cursor back

                    // whether or not a new query, update parameters in the history
                    if (history.replaceState) {
                        history.replaceState(params, document.title, '?action=search' + q_encoded);
                    }

                    // set current filter tab *after* updating the history
                    if (params.newQuery || params.updateSidebar) {
                        ODE.search.selectedTab = '';
                        ODE.search.switch_tabs($('#tab' + params.selectedTab)[0]);
                    }

                    // if a reloaded or global query, we need to reset all the filter checkboxes
                    if (params.updateSidebar) {
                        ODE.search.update_filters('Tiers', params['filterGroups[]']);
                    }

                    var canRedirect = params.newQuery;

                    // unmark this as a new or reloaded query
                    params.newQuery = false;
                    params.updateSidebar = false;

                    ODE.search.active_params = null;
                    ODE.search.last_params = params; // and save

                    // if only one result returned, redirect, unless we've redirected before
                    if ($('input#resultsList').data('gscount') == 1 && canRedirect) {
                        params.redirected = true; // so that we don't try redirecting after this
                        $('a[name=viewGeneset]')[0].click();
                    }
                }
            );

            return false;
        },

        switch_tabs: function (tab) {
            var tabName = tab.id.substr(3);
            if (ODE.search.selectedTab != tabName) {
                if (ODE.search.selectedTab) { // hide old
                    $('#tab' + ODE.search.selectedTab)[0].className = '';
                    $('#tab' + ODE.search.selectedTab + 'Content')[0].style.display = 'none';
                }
                // show new
                tab.className = 'selected';
                $('#tab' + tabName + 'Content')[0].style.display = 'block';

                // save
                ODE.search.selectedTab = tabName;
                if (history.state) { // could be old IE...blegh.
                    history.state.selectedTab = tabName;
                    history.replaceState(history.state, document.title);
                }
            }
        },

        // button: button jQuery object
        // menu: div jQuery object
        toggle_dropdown: function (button, menu) {
            if (!button.hasClass('clicked')) {
                // make sure dropdown is at least as wide as button
                menu.css('min-width', button.outerWidth());
                menu.slideDown();
                menu.position({
                    of: button,
                    at: 'right bottom',
                    my: 'right top',
                    collision: 'none'
                });

                button.toggleClass('clicked');

                // add code to hide the div when the user clicks outside of it
                $(document).bind('mouseup', function (e) {
                    if (menu[0] !== e.target && menu.has(e.target).length === 0) {
                        menu.slideUp('fast');
                        $(document).unbind(e);
                        if (button[0] !== e.target) { // if the button was clicked, handle below
                            button.toggleClass('clicked');
                        }
                    }
                });
            } else { // button was clicked while toggled "on;" unclick it.
                button.toggleClass('clicked');
            }
        },

        // grab checked genesets and run a tool on them
        // c.f. with ODE.analyze.validate and ODE.add_to_project
        validate_tool_form: function (tool_name) {
            // append a hidden list of geneset ids to the form
            var gsids = $('#toolForm_gsidsContainer');
            gsids.html(''); // clear any old gsids
            var gs_count = 0;

            // in the genesets page, there's a "Select All Results" checkbox;
            // if this is checked, we need to grab all the results from the server
            if ($('#selectAllResults') && $('#selectAllResults').attr('checked')) {
                gs_count = $('#resultsList').data('gscount');
                $($('#resultsList').data('gsids').split(',')).each(function (k, v) {
                    gsids.append('<input type="hidden" name="gs_id[]" value="' + v + '"/>');
                });
            } else {
                $(':checkbox[name="gs_id[]"]:checked').each(function () {
                    ++gs_count;
                    gsids.append('<input type="hidden" name="gs_id[]" value="' + this.value + '"/>');
                });
            }

            // must have at least two genesets
            if (gs_count < 2) {
                window.alert('Please select at least two GeneSets.');
                return false;
            }

            $('#real_tool').val(tool_name); // specify the tool to use
        }
    };

}).call(ODE);

