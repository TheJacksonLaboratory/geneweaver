#!/usr/bin/env python

## file: batch.py
## desc: Batch file reader.
## auth: Baker
##       TR
#

from collections import Counter as mset
from collections import defaultdict as dd
from copy import deepcopy
import re
from typing import Union, Tuple, Match

import geneweaverdb as gwdb
from pubmedsvc import get_pubmed_info

def make_digrams(s):
    """
    Recursively creates an exhaustive list of digrams from the given string.

    arguments
        s: string to generate digrams with

    returns
        a list of digram strings.
    """

    if len(s) <= 2:
        return [s]

    b = make_digrams(s[1:])
    b.insert(0, s[:2])

    return b

def calculate_str_similarity(s1, s2):
    """
    Calculates the percent similarity between two strings. Meant to be a
    replacement for PHP's similar_text function, which old GeneWeaver uses
    to determine the right microarray platform to use.
    This algorithm uses digram intersections determine percent similarity. 
    It is calculated as:

    sim(s1, s2) = (2 * intersection(digrams(s1), digrams(s2)) /
                   |digrams(s1) + digrams(s2)|

    arguments
        s1: string #1
        s2: string #2

    returns
        a float indicating the percent similarity between two strings
    """

    sd1 = make_digrams(s1)
    sd2 = make_digrams(s2)
    intersect = list((mset(sd1) & mset(sd2)).elements())

    return (2 * len(intersect)) / float(len(sd1) + len(sd2))

class BatchReader(object):
    """
    Class used to read and parse batch geneset files.

    public
        contents:   list of lines in the batch file
        usr_id:     ID of the user uploading the batch file
        genesets:   list of dicts representing the parsed genesets, each dict
                    has fields corresponding to columns in the geneset table
        errors:     list of strings indicating critical errors found during 
                    parsing
        warns:      list of strings indicating non-crit errors found during 
                    parsing

    private
        _parse_set:         the gene set currently being parsed
        _pub_map:           PMID -> pub_id mapping
        _symbol_cache:      a series of nested dicts used to map species
                            specific gene symbols to GW identifiers. The 
                            structure is: 
                                sp_id -> gdb_id -> ode_ref_id -> ode_gene_id
        _annotation_cache:  mapping of ontology term IDs -> ont_ids
    """

    def __init__(self, contents, usr_id=0):

        self.contents = contents
        self.usr_id = usr_id
        self.genesets = []
        self.errors = []
        self.warns = []
        self._parse_set = {}
        self._pub_map = None
        self._symbol_cache = dd(lambda: dd(int))
        self._annotation_cache = dd(int)

    def __reset_parsed_set(self):
        """
        Clears and resets the fields of the gene set currently being parsed. If
        the parsed set contains gene values we can assume it is complete (this
        assumption is checked later) and store it in the list of parsed sets.
        """

        if 'values' in self._parse_set and self._parse_set['values']:
            self.genesets.append(deepcopy(self._parse_set))

        if 'pmid' not in self._parse_set:
            self._parse_set['pmid'] = ''

        if 'usr_id' not in self._parse_set:
            self._parse_set['usr_id'] = 0

        if 'at_id' not in self._parse_set:
            self._parse_set['at_id'] = None

        if 'cur_id' not in self._parse_set:
            self._parse_set['cur_id'] = 5
            self._parse_set['gs_groups'] = '-1'

        self._parse_set['gs_name'] = ''
        self._parse_set['gs_description'] = ''
        self._parse_set['gs_abbreviation'] = ''
        self._parse_set['values'] = []
        self._parse_set['annotations'] = []

    def __check_parsed_set(self):
        """
        Checks to see if all the required fields are filled out for the gene
        set currently being parsed.

        returns
            true if all required fields are filled out otherwise false
        """

        if not self._parse_set['gs_name'] or\
           not self._parse_set['gs_description'] or\
           not self._parse_set['gs_abbreviation'] or\
           'gs_gene_id_type' not in self._parse_set or\
           'gs_threshold_type' not in self._parse_set or\
           'sp_id' not in self._parse_set:
               return False

        return True

    def __parse_score_type(self, s):
        """
        Attempts to parse out the score type and any threshold value
        from the given string.
        Acceptable score types and threshold values include:
            Binary
            P-Value < 0.05
            Q-Value < 0.05
            0.40 < Correlation < 0.50
            6.0 < Effect < 22.50
           
        The numbers listed above are only examples and can vary depending on
        geneset. If those numbers can't be parsed for some reason, default values
        (e.g. 0.05) are used. The score types are converted into a numeric
        representation used by the GW DB:

            P-Value = 1
            Q-Value = 2
            Binary = 3
            Correlation = 4
            Effect = 5

        arguments
            s: string containing score type and possibly threshold value(s)

        returns
            a tuple containing the threshold type and threshold value. 
                i.e. (gs_threshold_type, gs_threshold)
        """

        ## The score type, a numeric value but currently stored as a string
        stype = ''
        ## Default theshold values
        thresh = '0.05'

        ## Binary threshold is left at the default of 1
        if s.lower() == 'binary':
            stype = 3
            thresh = '1'

        elif s.lower().find('p-value') != -1:
            # validate value with p-value pattern
            valid, match = self.validate_pq_value(s.lower())
            stype = 1

            if valid:
                thresh = match.group(1)
            else:
                self.warns.append('Invalid threshold. Using p < 0.05.')

        elif s.lower().find('q-value') != -1:
            # validate value with q-value pattern
            valid, match = self.validate_pq_value(s.lower())
            stype = 2

            if valid:
                thresh = match.group(1)
            else:
                self.warns.append('Invalid threshold. Using q < 0.05.')

        elif s.lower().find('correlation') != -1:
            # validate correlation range
            valid, match = self.validate_correlation_range(s.lower())
            stype = 4

            if valid:
                thresh = match.group(1) + ',' + match.group(2)
            else:
                thresh = ','
                self.warns.append(
                    'Invalid threshold. No default threshold set for correlation.'
                ) 

        elif s.lower().find('effect') != -1:
            # validate effect range
            valid, match = self.validate_effect_range(s.lower())
            stype = 5

            if valid:
                thresh = match.group(1) + ',' + match.group(2)
            else:
                thresh = ','
                self.warns.append('Invalid threshold. No default threshold set for effect.')

        else:
            self.errors.append('An unknown score type (%s) was provided.' % s)

        return (stype, thresh)

    @staticmethod
    def validate_pq_value(value: str) -> Tuple[bool, Union[Match, None]]:
        """
        Validates whether the given string matches the format of a p-value or q-value.

        The value is expected to be a numeric value between 0 and 1, inclusive.

        Regex Pattern:
            r"^(0(\.\d+)?|1(\.0+)?)$"

        Explanation:
        1. **`^`**: Anchors the match to the start of the string.
        2. **`0(\.\d+)?`**:
           - Matches the number `0`.
           - `(\.\d+)?`: Optionally matches a decimal point (`.`) followed by one or more digits (`\d+`).
             - Examples: `0`, `0.5`, `0.123`.
        3. **`|`**: Logical OR operator, allowing the regex to match either the `0` part or the `1` part.
        4. **`1(\.0+)?`**:
           - Matches the number `1`.
           - `(\.0+)?`: Optionally matches a decimal point (`.`) followed by one or more zeros (`0+`).
             - Examples: `1`, `1.0`, `1.000`.
        5. **`$`**: Anchors the match to the end of the string.

        Arguments:
            value (str): The string to validate.

        Returns:
            tuple:
                - bool: True if the value is valid, False otherwise.
                - re.Match | None: The match object if the string matches the format, None otherwise.

        Example:
            validate_pq_value("0.05") -> (True, <Match object>)
            validate_pq_value("1.5") -> (False, None)
        """
        # Regex pattern for validating p-value or q-value (e.g., 0.05, 1.0)
        pq_value_regex = r"^(0(\.\d+)?|1(\.0+)?)$"
        match = re.match(pq_value_regex, value)
        if match:
            return True, match
        return False, None

    @staticmethod
    def validate_correlation_range(value: str) -> Tuple[bool, Union[Match, None]]:
        """
        Validates whether the given string matches the format of a correlation range.

        The correlation range is expected to be in the format:
        `<lower_bound> < correlation < <upper_bound>`, where:
        - `<lower_bound>` and `<upper_bound>` are numeric values (integer or decimal).
        - `Correlation` is a keyword separating the bounds.
        - `<` is the comparison operator.

        Arguments:
            value (str): The string to validate.

        Returns:
            tuple:
                - bool: True if the range is valid and the lower bound is less than the upper bound, False otherwise.
                - re.Match | None: The match object if the string matches the format, None otherwise.

        Example:
            validate_correlation_range("-0.75 < correlation < 0.75") -> (True, <Match object>)
            validate_correlation_range("1 < correlation < -1") -> (False, None)
        """

        # Regex pattern for validating correlation range (e.g., -0.75 < Correlation < 0.75)
        # Explanation:
        # 1. `^-?` allows an optional negative sign for the first number.
        # 2. `[0-9]+(\.[0-9]+)?` matches integers or decimals.
        # 3. `<` ensures the presence of the comparison operator.
        # 4. `-?` allows an optional negative sign for the second number.
        # 5. `[0-9]+(\.[0-9]+)?` matches the second numeric value.
        correlation_range_regex = r"^(-?[0-9]+(\.[0-9]+)?)\s*<\s*correlation\s*<\s*(-?[0-9]+(\.[0-9]+)?)$"
        match = re.match(correlation_range_regex, value)
        if match:
            # Extract the numerical values
            lower_bound = float(match.group(1))
            upper_bound = float(match.group(3))
            # Ensure the first number is less than the second
            if lower_bound < upper_bound:
                return True, match
        return False, None

    @staticmethod
    def validate_effect_range(value: str) -> Tuple[bool, Union[Match, None]]:
        """
        Validates whether the given string matches the format of an effect range.

        The effect range is expected to be in the format:
        `<lower_bound> < effect < <upper_bound>`, where:
        - `<lower_bound>` and `<upper_bound>` are numeric values (integer or decimal).
        - `Effect` is a keyword separating the bounds.
        - `<` is the comparison operator.

        Arguments:
            value (str): The string to validate.

        Returns:
            tuple:
                - bool: True if the range is valid and the lower bound is less than the upper bound, False otherwise.
                - re.Match | None: The match object if the string matches the format, None otherwise.

        Example:
            validate_effect_range("6.0 < effect < 22.50") -> (True, <Match object>)
            validate_effect_range("10 < effect < -5") -> (False, None)
        """

        # Regex pattern for validating effect range (e.g., 6.0 < Effect < 22.50)
        # Explanation:
        # 1. `^-?[0-9]+(\.[0-9]+)?` matches the first numeric value, allowing optional negative signs and decimals.
        # 2. `<\s*effect\s*<` ensures the presence of the comparison operator and the word `effect` with optional spaces.
        # 3. `-?[0-9]+(\.[0-9]+)?$` matches the second numeric value, allowing optional negative signs and decimals.
        effect_range_regex = r"^(-?[0-9]+(\.[0-9]+)?)\s*<\s*effect\s*<\s*(-?[0-9]+(\.[0-9]+)?)$"

        # Match the input string against the regex pattern
        match = re.match(effect_range_regex, value)
        if match:
            # Extract the numerical values
            lower_bound = float(match.group(1))
            upper_bound = float(match.group(3))
            # Ensure the first number is less than the second
            if lower_bound < upper_bound:
                return True, match
        return False, None

    def __parse_gene_type(self, gtype, platforms, gene_types):
        """
        Parses and determines the gene type the user has provided. If the gene
        type is a microarray, this will attempt to find a matching platform.
        Otherwise it will use regular gene types from the genedb table.

        arguments
            gtype:      the gene type string being parsed
            platforms:  dict mapping platform names -> gene type ids (gdb_id)
            gene_types: dict mapping regular gene type names -> gene type ids

        returns
            an gdb_id (integer) or None if no gene type could be parsed/found
        """

        ## If a microarray platform is specified, we use string
        ## similarity to find the best possible platform in our DB. The
        ## best match above a threshold is used. This has to be done
        ## since naming conventions for the same platform can vary.
        ## All other gene types are easier to handle; they are 
        ## retrieved from the DB and their ID types are negated. 
        if gtype.lower().find('microarray') != -1:
            ## Remove 'microarray' text
            gtype = gtype[len('microarray'):].strip()
            original = gtype

            ## Determine the closest microarry platform match above a 70%
            ## similarity threshold.
            best = 0.70

            for plat, pid in platforms.items():
                sim = calculate_str_similarity(plat.lower(), original.lower())

                if sim > best:
                    best = sim
                    gtype = plat

            ## Convert to the parsed gene ID type to an actual ID. 
            ## gene will now be an integer
            gtype = platforms.get(gtype, 'unknown')

            if type(gtype) != int:
                self.errors.append('%s is an invalid platform' % original)

            else:
                return gtype

        ## Otherwise the user specified one of the gene types, not a
        ## microarray platform
        ## :IMPORTANT: Gene ID representation is fucking ass backwards.
        ## Expression platforms have positive (+) gs_gene_id_types 
        ## while all other types (e.g. symbols) should have negative 
        ## (-) integer ID types despite their gdb_ids being positive.
        else:
            gtype = gtype.lower()

            if gtype not in gene_types:
                self.errors.append('%s is an invalid gene type' % gtype)

            else:
                ## Convert to a negative integer (gdb_id)
                return -gene_types[gtype]

        return None

    def __parse_batch_syntax(self, lns):
        """
        Parses a batch file according to the format listed on
        http://geneweaver.org/index.php?action=manage&cmd=batchgeneset
        The results (gene set objects) and any errors or warnings are stored in
        their respective class attributes. 

        arguments
            lns: list of strings, one for each line in the batch file
        """

        self.__reset_parsed_set()

        #gene_types = db.get_gene_types()
        #species = db.get_species()
        #platforms = db.get_platform_names()

        type_list = gwdb.get_gene_id_types()
        sp_dict = gwdb.get_all_species()
        plat_list = gwdb.get_microarray_types()
        gene_types = {}
        species = {}
        platforms = {}

        ## Provide lower cased keys for gene types, species, and expression
        ## platformrs. Otherwise batch files must use case sensitive fields
        ## which would be annoying. Also do some rearranging since the
        ## geneweaverdb functions differ from mine.
        #for gdb_name, gdb_id in gene_types.items():
        for d in type_list:
            gene_types[d['gdb_name'].lower()] = d['gdb_id']

        for sp_id, sp_name in sp_dict.items():
            species[sp_name.lower()] = sp_id

        for d in plat_list:
            platforms[d['pf_name'].lower()] = d['pf_id']

        for i in range(len(lns)):
            lns[i] = lns[i].strip()

            ## These are special (dev only) additions to the batch file that 
            ## allow tiers, user IDs, and attributions to be specified. These
            ## are only used in the public resource uploader scripts.
            #
            ## Lines beginning with 'T' are Tier IDs
            if lns[i][:2] == 'T ':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['cur_id'] = int(lns[i][1:].strip())

            ## Lines beginning with 'U' are user IDs
            elif lns[i][:2] == 'U ':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['usr_id'] = int(lns[i][1:].strip())

            ## Lines beginning with 'D' are attribution abbrevations
            elif lns[i][:2] == 'D ':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['at_id'] = lns[i][1:].strip()

            ## :, =, + is required for each geneset in the batch file
            #
            ## Lines beginning with ':' are geneset abbreviations (REQUIRED)
            elif lns[i][:1] == ':':
                ## This checks to see if we've already read, parsed, and stored
                ## some gene values. If we have, that means we can save the
                ## currently parsed geneset, clear out any REQUIRED fields before 
                ## we do more parsing, and begin parsing this new set.
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['gs_abbreviation'] = lns[i][1:].strip()

            ## Lines beginning with '=' are geneset names (REQUIRED)
            elif lns[i][:1] == '=':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['gs_name'] = lns[i][1:].strip()

            ## Lines beginning with '+' are geneset descriptions (REQUIRED)
            elif lns[i][:1] == '+':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['gs_description'] += lns[i][1:].strip()
                self._parse_set['gs_description'] += ' '

            ## !, @, %, are required but can be omitted from later sections if
            ## they don't differ from the first. Meaning, these fields can be
            ## specified once and will apply to all gene sets in the file unless
            ## this field is encountered again.
            #
            ## Lines beginning with '!' are score types (REQUIRED)
            elif lns[i][:1] == '!':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                ttype, threshold = self.__parse_score_type(lns[i][1:].strip())

                ## An error ocurred 
                if not ttype:
                    ## Appends the line number to the last error which should
                    ## be the error indicating an unknown score type was used
                    self.errors[-1] = 'LINE %s: %s' % (i + 1, self.errors[-1])

                else:
                    self._parse_set['gs_threshold_type'] = ttype
                    self._parse_set['gs_threshold'] = threshold

            ## Lines beginning with '@' are species types (REQUIRED)
            elif lns[i][:1] == '@':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                spec = lns[i][1:].strip()

                if spec.lower() not in species:
                    self.errors.append(
                        'LINE %s: %s is an invalid species' % (i + 1, spec)
                    )

                else:
                    ## Convert to sp_id
                    self._parse_set['sp_id'] = species[spec.lower()]

            ## Lines beginning with '%' are gene ID types (REQUIRED)
            elif lns[i][:1] == '%':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                gene = lns[i][1:].strip()
                gene = self.__parse_gene_type(gene, platforms, gene_types)

                ## An error ocurred 
                if not gene:
                    ## Appends the line number to the last error which should
                    ## be the error indicating an invalid gene type
                    self.errors[-1] = 'LINE %s: %s' % (i + 1, self.errors[-1])

                else:
                    self._parse_set['gs_gene_id_type'] = gene
                            

            ## Lines beginning with 'P ' are PubMed IDs (OPTIONAL)
            elif (lns[i][:2] == 'P ') and (len(lns[i].split('\t')) == 1):
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['pmid'] = lns[i][1:].strip()

            ## Lines beginning with 'A' are groups, default is private (OPTIONAL)
            elif lns[i][:2] == 'A ' and (len(lns[i].split('\t')) == 1):
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                group = lns[i][1:].strip()

                ## If the user gives something other than private/public,
                ## automatically make it private
                if group.lower() != 'private' and group.lower() != 'public':
                    self._parse_set['gs_groups'] = '-1'
                    self._parse_set['cur_id'] = 5

                ## Public data sets are initially thrown into the provisional
                ## Tier IV. Tier should never be null.
                elif group.lower() == 'public':
                    self._parse_set['gs_groups'] = '0'
                    self._parse_set['cur_id'] = 4

                ## Private
                else:
                    self._parse_set['gs_groups'] = '-1'
                    self._parse_set['cur_id'] = 5

            ## Lines beginning with '~' are ontology annotations (OPTIONAL)
            elif lns[i][:2] == '~ ':
                if self._parse_set['values']:
                    self.__reset_parsed_set()

                self._parse_set['annotations'].append(lns[i][1:].strip())

            ## Lines beginning with '#' are comments
            elif lns[i][:1] == '#':
                continue

            ## Skip blank lines
            elif lns[i][:1] == '':
                continue

            ## If the lines are tab separated, we assume it's the gene data that
            ## will become part of the geneset_values. Also (reluctantly)
            ## support single spaces instead of tabs since people are gonna do
            ## it anyway and some of our examples keep getting their tabs
            ## converted.
            elif len(lns[i].split('\t')) == 2 or len(lns[i].split()) == 2:

                ## Check to see if all the required data was specified, if not
                ## this set can't get uploaded. Let the user figure out what the
                ## hell they're missing cause telling them is too much work on
                ## our part.
                if not self.__check_parsed_set():

                    err = 'One or more of the required fields are missing.'

                    ## Otherwise this string will get appended a bajillion times
                    if err not in self.errors:
                        self.errors.append(err)

                else:
                    lns[i] = lns[i].split()

                    self._parse_set['values'].append((lns[i][0], lns[i][1]))

            ## Who knows what the fuck this line is, just skip it
            else:
                self.warns.append(
                    'LINE %s: Skipping line with unknown identifiers (%s)' % 
                    ((i + 1), lns[i])
                )

        ## awwww shit, we're finally finished! Make the final parsed geneset.
        if self.__check_parsed_set():
            self.genesets.append(self._parse_set)

    def __insert_geneset_file(self, genes):
        """
        Modifies the geneset_values into the proper format for storage in the file
        table and inserts the result.

        arguments
            genes: a list of tuples representing gene set values
                   e.g. [('Mobp', 0.001), ('Daxx', 0.2)]

        returns
            the file_id (int) of the newly inserted file
        """

        conts = ''

        for tup in genes:
            conts += '%s\t%s\n' % (tup[0], tup[1])

        return gwdb.insert_file(conts, '')

    def __map_ontology_annotations(self, gs):
        """
        If a gene set has ontology annotations, we map the ontology term IDs to
        the internal IDs used by GW (ont_ids) and save them in the gene set
        object.
        """

        gs['ont_ids'] = []

        for anno in gs['annotations']:

            ## Check the cache of retrieved annotations
            if self._annotation_cache[anno]:
                gs['ont_ids'].append(self._annotation_cache[anno])

            else:
                ## Will return a single element list, get rid of the list part
                ont_id = gwdb.get_ontologies_by_refs([anno])
                ont_id = ont_id[0]

                if ont_id:
                    gs['ont_ids'].append(ont_id)

                    self._annotation_cache[anno] = ont_id

                else:
                    self.warns.append(
                        'The ontology term %s is missing from GW' % anno
                    )

    def __map_gene_identifiers(self, gs):
        """
        Maps the user provided gene symbols (ode_ref_ids) to ode_gene_ids.
        The mapped genes are added to the gene set object in the 
        'geneset_values' key. This added key is a list of triplets containing
        the user uploaded symbol, the ode_gene_id, and the value.
            e.g. [('mobp', 1318, 0.03), ...]

        arguments
            gs: a dict representing a geneset. Contains fields with the same
                columns as the geneset table

        returns
            an int indicating the total number of geneset_values inserted into
            the DB.
        """

        ## Isolate gene symbols (ode_ref_ids)
        gene_refs = [x[0] for x in gs['values']]
        gene_type = gs['gs_gene_id_type']
        sp_id = gs['sp_id']
        gs['geneset_values'] = []

        ## Check to see if we have cached copies of these references. If we do,
        ## we don't have to make any DB calls or build the mapping
        if self._symbol_cache[sp_id][gene_type]:
            pass

        ## Negative numbers indicate normal gene types (found in genedb) while
        ## positive numbers indicate expression platforms and more work :(
        elif gs['gs_gene_id_type'] < 0:
            ## A mapping of (symbols) ode_ref_ids -> ode_gene_ids. The
            ## ode_ref_ids returned by this function have all been lower cased.
            ## Remember gene_type is negative.
            ref2ode = gwdb.get_gene_ids_by_spid_type(sp_id, -gene_type)

            self._symbol_cache[sp_id][gene_type] = dd(int, ref2ode)

        ## It's a damn expression platform :/
        else:
            ## This is a mapping of (symbols) prb_ref_ids -> prb_ids for the
            ## given platform
            ref2prbid = gwdb.get_platform_probes(gene_type)
            ## This is a mapping of prb_ids -> ode_gene_ids
            prbid2ode = gwdb.get_probe2gene(list(ref2prbid.values()))

            ## Just throw everything in the same dict, shouldn't matter since
            ## the prb_refs will be strings and the prb_ids will be ints
            self._symbol_cache[sp_id][gene_type] = dd(int)
            self._symbol_cache[sp_id][gene_type].update(ref2prbid)
            self._symbol_cache[sp_id][gene_type].update(prbid2ode)

        ref2ode = self._symbol_cache[sp_id][gene_type]

        ## duplicate detection
        dups = dd(str)
        total = 0

        for ref, value in gs['values']:

            ## Platform handling
            if gs['gs_gene_id_type'] > 0:
                prb_id = ref2ode[ref]
                odes = ref2ode[prb_id]

                if not prb_id or not odes:
                    self.warns.append('No gene/locus data exists for %s' % ref)
                    continue

                ## Yeah one probe reference may be associated with more than
                ## one gene/ode_gene_id, it's fucking weird. I think this is
                ## specific to affymetrix platforms
                for ode in odes:
                    ## Check for duplicate ode_gene_ids, otherwise postgres
                    ## bitches during value insertion
                    if not dups[ode]:
                        dups[ode] = ref

                    else:
                        self.warns.append(
                            '%s and %s are duplicates, only %s was added'
                            % (ref, dups[ode], dups[ode])
                        )
                        continue

                    gs['geneset_values'].append((ref, ode, value))

            ## Not platform stuff
            else:

                ## Case insensitive symbol identification
                refl = ref.lower()

                if not ref2ode[refl]:
                    self.warns.append('No gene/locus exists data for %s' % ref)
                    continue

                ode = ref2ode[refl]

                ## Prevent postgres bitching again
                if not dups[ode]:
                    dups[ode] = ref

                else:
                    self.warns.append(
                        '%s and %s are duplicates, only %s was added'
                        % (ref, dups[ode], dups[ode])
                    )
                    continue

                gs['geneset_values'].append((ref, ode, value))

        return len(gs['geneset_values'])

    def __check_thresholds(self, ttype, threshold, value):
        """
        Checks to see whether or not the gene set values fall within the score
        threshold associated with the set.

        arguments
            ttype:      integer indicating the gene set threshold type
            threshold:  value representing the threshold; depending on the
                        threshold type this may be a single numeric value, or a
                        list of two numeric values ([min, max])
            value:      probably a string representing the gene value

        returns
            A boolean indicating whether or not the value falls within the
            range specified by the threshold
        """

        value = float(value)

        ## P and Q values
        if ttype == 1 or ttype == 2:
            if value <= threshold:
                return True

        ## Correlation and effect scores
        elif ttype == 4 or ttype == 5:
            if value >= threshold[0] and value <= threshold[1]:
                return True

        ## Binary
        else:
            if value >= threshold:
                return True

        return False

    def __insert_geneset_values(self, gs):
        """
        Inserts gene set values into the DB.

        arguments
            gs: gene set object
        """

        ttype = gs['gs_threshold_type']
        thresh = None
        is_threshold_set = True

        if ttype == 1 or ttype == 2 or ttype == 3:
            thresh = float(gs['gs_threshold'])

        elif ttype == 4 or ttype == 5:
            if gs['gs_threshold'] == ',':
                is_threshold_set = False
            else:
                thresh = list(map(float, gs['gs_threshold'].split(',')))

        ## This should never happen
        else:
            thresh = 1.0

        for ref, ode, value in gs['geneset_values']:
            # all gs values should be within threshold if the gs threshold is not set
            if not is_threshold_set:
                gs_value_in_threshold = True
            else:
                gs_value_in_threshold = self.__check_thresholds(ttype, thresh, value)

            gwdb.insert_geneset_value(
                gs['gs_id'], ode, value, ref, 
                gs_value_in_threshold
            )

    def __insert_annotations(self, gs):
        """
        Inserts gene set ontology annotations into the DB.

        arguments
            gs: gene set object
        """

        if 'ont_ids' in gs:
            for ont_id in set(gs['ont_ids']):
                gwdb.add_ont_to_geneset(
                    gs['gs_id'], ont_id, 'GeneWeaver Primary Annotation'
                )

    def parse_batch_file(self, bs='', usr_id=0):
        """
        Parses a batch file to completion. 

        arguments
            bs:     string containing the contents of the batch file
            usr_id: ID of the user uploading the gene sets

        returns
            A list of gene set objects (dicts) with properly filled out fields,
            ready for insertion into the GW DB.
        """

        ## errors that prevent further parsing
        self.errors = []
        ## warnings generated during parsing
        self.warns = []
        ## list of gs_ids successfully added to the db
        added = []  

        if not bs:
            bs = self.contents

        if not usr_id:
            usr_id = self.usr_id

        self.__parse_batch_syntax(bs)

        if self.errors:
            return []

        ## The attribution stuff can probably be safely removed b/c it's only 
        ## used for up(load|dat)ing public resource data and users shouldn't be
        ## able to specify at_ids
        #attributions = db.get_attributions()
        # TODO: This should be fixed
        attributions = gwdb.get_all_attributions()
        attributions_sub = gwdb.get_all_attributions()

        for at_id, abbrev in attributions.items():
            ## Fucking NULL row in the db, this needs to be removed
            if abbrev:
                attributions_sub[abbrev.lower()] = at_id
        attributions = attributions_sub

        ## Geneset post-processing: mapping gene -> ode_gene_ids, attributions,
        ## annotations, and the user ID
        for gs in self.genesets:

            gs['usr_id'] = usr_id
            gs['gs_count'] = self.__map_gene_identifiers(gs)

            if gs['at_id']:
                gs['gs_attribution'] = attributions.get(gs['at_id'], None)

            self.__map_ontology_annotations(gs)

        return self.genesets

    def get_geneset_pubmeds(self):
        """
        Retrieves publication info for all gene sets that have PMIDs attached.
        If the PMID already exists in the DB that entry is used otherwise
        publication data is downloaded from NCBI.
        """

        ## PMID -> pub_id map
        if not self._pub_map:
            self._pub_map = gwdb.get_publication_mapping()

        ## These publications already exist in the DB
        found = [g for g in self.genesets if g['pmid'] in self._pub_map]
        ## These don't
        not_found = [g for g in self.genesets if g['pmid'] not in self._pub_map]

        for gs in found:
            gs['pub_id'] = self._pub_map[gs['pmid']]
            gs['pub'] = gs['pmid']

        #pubs = get_pubmed_articles(map(lambda g: g['pmid'], self.genesets))
        for gs in not_found:
            ## Check to see if the PMID has been added to the cache
            if gs['pmid'] in self._pub_map:
                gs['pub_id'] = self._pub_map[gs['pmid']]
                gs['pub'] = gs['pmid']

            ## Get the info from NCBI
            else:
                gs['pub_id'] = None

                if gs['pmid']:
                    gs['pub'] = get_pubmed_info(gs['pmid'])
                else:
                    gs['pub'] = None

    def insert_genesets(self):
        """
        Inserts parsed gene sets along with their files, values, and 
        annotations into the DB.

        returns
            the gs_ids of the inserted sets
        """

        ids = []

        for gs in self.genesets:

            if not gs['gs_count']:

                self.errors.append((
                    'No genes in the set %s mapped to GW identifiers so it '
                    'was not uploaded'
                ) % gs['gs_name'])

                continue

            if not gs['pub_id'] and gs['pub']:
                gs['pub_id'] = gwdb.insert_publication(gs['pub'])

            gs['file_id'] = self.__insert_geneset_file(gs['values'])
            gs['gs_id'] = gwdb.insert_geneset(gs)
            self.__insert_geneset_values(gs)
            self.__insert_annotations(gs)

            ids.append(gs['gs_id'])

        return ids
