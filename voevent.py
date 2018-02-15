import sys
import re
import json
from datetime import datetime, timedelta
from collections import namedtuple
from pprint import pprint
import xml.etree.ElementTree as ET


Position2D = namedtuple('Position2D', ['ra', 'dec', 'error'])
Param = namedtuple('Param', ['value', 'unit', 'ucd'])


def json_serializer_helper(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))


def parse_element(element, conversion='force', stripws=True):
    attribs = element.attrib
    datatype = attribs.get('dataType')
    if element.text:
        text = (element.text.strip() if stripws else element.text)
    else:
        text = None

    if attribs.get('value'):
        value = convert_value(
            attribs['value'], conversion=conversion, datatype=datatype)
    elif text:
        value = convert_value(
            text, conversion=conversion, datatype=datatype)
    else:
        value = None

    name = element.tag
    if attribs.get('name'):
        name = attribs['name']

    for key, val in attribs.items():
        if key == 'value':
            continue
        attribs[key] = convert_value(val, conversion=conversion)

    return {'tag': element.tag, 'name': name, 'text': text,
            'attributes': attribs, 'value': value}


def xml2python(element, conversion='force', stripws=True, parse_root=False):
    """Convert an XML element to a Python list-dict structure

    This converts an XML element structure to a verbose Python nested
    data structure of dicts inside a list. The list contains the
    children of the element, each as a dict.

    The dict structure has the following keys and values:

    - tag: string, name of the tag
    - text: string, text contents of the tag. Empty string is there is no text
    - attributes: the attributes of the tag, as a dict
    - children: a list of the children of the current child.
    - value: a value, deduced from the text or a 'value' attribute

    Values
    ------

    Each child contains a 'value' key, which contains the appropriate
    value for the tag. If the text of a tag is non-empty, this will be
    the value. If the text is empty, the value will be the value of
    the 'value' attribute in the tag. If the text is empty and the
    'value' attribute does not exist, the value is None.

    Values can be parsed into Python values. By default, values are
    strings (or None if no value could be deduced), but they can be
    parsed into integers, floats, False, True or datetime objects.

    See the 'conversion' argument section for moe details

    Arguments
    ---------

    - element: XML element

    - parse_root: bool, default False

        Whether to parse the root element itself, that is, the
        `element` itself.

        This changes the return format, from a list (of `element`
        children) to a dict contain the `element` tag, attributes,
        text, value and children.

    - conversion: one of 'force', 'always', 'given', 'none'

        Convert a value from a string into a Python value: a boolean
        (True, False), integer, float or datetime object, or a str if
        all conversions fail.

        The options are as follows:

        - force: always try to convert the value. This ignores the
          `dataType` attribute

        - always: try to convert the value. If the `dataType`
          attribute of a tag is present, this will force it to that
          type; otherwise, the most suitable data type is found.

        - given: only convert a value if the `dataType` attribute is
          present, and convert it to that type.

        - none: do not convert the value, even if the `dataType` is
          present.

        Note that the `dataType` attribute will be present as a dict
        element in the final output, so one can deduce what type of
        conversion has happened. Similarly, the text will be available
        in its original form (as a string), as will a `value`
        attribute. Only the `value` key in the child dict will have a
        parsed value.

        By default, the conversion is 'force'd, for convenience. For
        example, a "False" value attribute with a dataType "string"
        will be forced to a False boolean. Using 'always' or 'given'
        for conversion would have left this as a string, while still
        parsing other values. There are likely few cases where 'force'
        causes problems.

    - stripws: bool, default True

        Strip whitespace before storing a value

        This is convenient to remove newlines and spaces from `text`
        values. This may lose information, although this will be very
        limited.

        The default is to strip whitespace.

    Conversion to JSON
    ------------------

    The above data structure can be conveniently converted to JSON,
    except for `datetime` objects. A small helper function exists in
    this module: `json_serializer_helper(obj)`, that will convert a
    `datetime` object into an ISO-formatted string. Use this as
    follows:

        data = xml2python(xmltree.getroot())
        with open('data.json', 'w') as fp:
            json.dump(data, fp, default=json_serializer_helper)

    """

    data = []
    for child in element:
#        attribs = child.attrib
#        datatype = attribs.get('dataType')
#        if child.text:
#            text = (child.text.strip() if stripws else child.text)
#        else:
#            text = None
#        if attribs.get('value'):
#            value = convert_value(
#                attribs['value'], conversion=conversion, datatype=datatype)
#        elif text:
#            value = convert_value(
#                text, conversion=conversion, datatype=datatype)
#        else:
#            value = None
#        for key, val in attribs.items():
#            attribs[key] = convert_value(val, conversion=conversion)
        entry = parse_element(child, conversion=conversion, stripws=stripws)
        children = xml2python(child, conversion=conversion, stripws=stripws)
        entry['children'] = children
        data.append(entry)

    if parse_root:
        entry = parse_element(element, conversion=conversion, stripws=stripws)
        entry['children'] = data
        return entry

    return data


def convert_value(value, conversion='force', datatype=None):
    tmpval = value
    if conversion in ['force', 'always']:
        if tmpval is not None:
            if tmpval.lower() in ['true', 'yes']:
                value = True
            elif tmpval.lower() in ['false', 'no']:
                value = False
            else:
                try:
                    value = int(tmpval)
                except ValueError:
                    try:
                        value = float(tmpval)
                    except ValueError:
                        try:
                            date, fracsec = value.split('.', maxsplit=1)
                            fracsec = '0.' + fracsec
                        except ValueError:
                            date, fracsec = value, None
                        try:
                            date, time = value.split(maxsplit=1)
                            date = date + 'T' + time
                        except ValueError:
                            pass
                        try:
                            date = datetime.strptime(
                                date, '%Y-%m-%dT%H:%M:%S')
                            if fracsec:
                                date += timedelta(0, float(fracsec), 0)
                            value = date
                        except ValueError:
                            pass

    if conversion in ['always', 'given']:
        if tmpval:
            if datatype == 'int':
                value = int(tmpval)
            elif datatype == 'float':
                value = float(tmpval)
            elif datatype == 'string':
                value = str(tmpval)
            elif datatype in ['bool', 'boolean']:
                if value.lower() in ['true', 'yes']:
                    value = True
                elif value.lower() in ['false', 'no']:
                    value = False

    return value


class VOEvent:
    @classmethod
    def fromfile(cls, fileobj):
        tree = ET.parse(fileobj)
        return cls(tree)

    @classmethod
    def fromstring(cls, string):
        root = ET.fromstring(string)
        tree = ET(element=root)
        return cls(tree)

    def __init__(self, xmltree):
        self.xmltree = xmltree
        self.Who = None
        self.What = None
        self.WhereWhen = None
        self.How = None
        self.Why = None
        self.Citations = None
        self.Description = None
        self.Reference = None
        self.who = {}
        self.what = {}
        self.wherewhen = {}
        self.how = {}
        self.why = {}
        self.position2d = ()

    def parse(self, options=None):
        if options is None:
            self.options = {'conversion': 'force'}

        root = self.xmltree.getroot()
        regex = re.compile(
            "\{http://www\.ivoa\.net/xml/VOEvent/v\d(\.\d(\.\d)?)?}VOEvent")
        assert regex.search(root.tag), "bad XML root tag"
        attribs = root.attrib
        version = list(map(int, attribs['version'].split('.')))
        if len(version) == 1:
            major, minor = version[0], 0
        else:
            major, minor = version[:2]
        assert major == 2, "only VOEvent version 2 is supported"
        self.version = major, minor
        self.role = attribs['role']
        assert self.role in {'observation', 'prediction', 'utility', 'test'}, \
                "invalid role"
        self.ivorn = attribs['ivorn']
        keys = self.ivorn.split('/', maxsplit=4)
        authority = keys[2]
        resourcekey, localid = keys[3].split('#', maxsplit=1)
        self.eventid = dict(authority=authority,
                            resourcekey=resourcekey,
                            localid=localid)

        for key in ['who', 'what', 'wherewhen', 'how', 'why',
                    'citations', 'description', 'reference']:
            func = getattr(self, 'parse_' + key)
            func()

    def parse_who(self):
        Who = self.xmltree.getroot().findall('Who')
        assert len(Who) <= 1
        self.who = {}
        if Who:
            self.Who = Who[0]
            for child in self.Who:
                if child.tag == 'Description':
                    self.who['description'] = child.text
                elif child.tag == 'AuthorIVORN':
                    self.who['ivorn'] = child.text
                elif child.tag == 'Date':
                    self.who['date'] = convert_value(child.text)
                elif child.tag == 'Reference':
                    self.who['reference'] = child.text
                elif child.tag == 'Author':
                    author = {}
                    for grandchild in child:
                        keys1 = ['title', 'shortName', 'logoURL',
                                 'contactName', 'contactEmail', 'contactPhone',
                                 'contributor']
                        keys2 = ['title', 'short', 'logo', 'name', 'email',
                                 'phone', 'contributor']
                        for key1, key2 in zip(keys1, keys2):
                            if grandchild.tag == key1:
                                author[key2] = grandchild.text
                    self.who['author'] = author
        print('self.who =', end=' ')
        pprint(self.who)

    def parse_what_group(self, group):
        conversion = self.options['conversion']
        what = {}
        for el in group:
            if el.tag not in ['Param', 'Group']:
                continue
            name = el.attrib['name']
            if el.tag == 'Param':
                value = el.attrib.get('value')
                datatype = el.attrib.get('dataType')
                value = convert_value(value, conversion, datatype=datatype)
                what[name] = Param(value=value,
                                   unit=el.attrib.get('unit'),
                                   ucd=el.attrib.get('ucd'))
            elif el.tag == 'Group':
                what[name] = self.parse_what_group(el)
            else:
                raise ValueError("invalid What child tag")
        return what

    def parse_what(self):
        What = self.xmltree.getroot().findall('What')
        assert len(What) <= 1
        if What:
            self.What = What[0]
            self.what = self.parse_what_group(self.What)
        print('self.what =', end=' ')
        pprint(self.what)

    def parse_coord_system(self, el):
        self.coordsystem = None
        system = el.find('AstroCoordSystem')
        if system is not None:
            system = system.attrib['id']
            if system not in ["TT-ICRS-TOPO", "UTC-ICRS-TOPO", "TT-FK5-TOPO",
                              "UTC-FK5-TOPO", "GPS-ICRS-TOPO", "GPS-ICRS-TOPO",
                              "GPS-FK5-TOPO", "GPS-FK5-TOPO", "TT-ICRS-GEO",
                              "UTC-ICRS-GEO", "TT-FK5-GEO", "UTC-FK5-GEO",
                              "GPS-ICRS-GEO", "GPS-ICRS-GEO", "TDB-ICRS-BARY",
                              "TDB-FK5-BARY", "UTC-GEOD-TOPO"]:
                raise ValueError("coordinate system is not a valid system")
        return system

    def parse_wherewhen(self):
        WhereWhen = self.xmltree.getroot().findall('WhereWhen')
        assert len(WhereWhen) <= 1
        self.wherewhen = {}
        if WhereWhen:
            self.WhereWhen = WhereWhen[0]
            obsloc = self.WhereWhen.find('ObsDataLocation/ObservationLocation')
            pos = obsloc.find('AstroCoords/Position2D')
            if pos is not None:
                name1 = pos.find('Name1')
                name2 = pos.find('Name2')
                if (name1 is not None and name2 is not None and
                    name1.text == 'RA' and name2.text == 'Dec'):
                    ra = pos.find('Value2/C1')
                    dec = pos.find('Value2/C2')
                    error = pos.find('Error2Radius')
                    if error is not None:
                        error = float(error.text)
                    if ra is not None and dec is not None:
                        self.position2d = Position2D(ra=float(ra.text),
                                                   dec=float(dec.text),
                                                   error=error)
                    self.wherewhen['position2d'] = self.position2d
            self.coordsystem = self.parse_coord_system(obsloc)
            self.wherewhen['system'] = self.coordsystem
            time = obsloc.find('AstroCoords/Time/TimeInstant/ISOTime')
            if time is not None:
                time = convert_value(time.text)
            self.coordtime = time
            self.wherewhen['time'] = time

        print('coord system =', self.coordsystem, '; coord time =', self.coordtime)
        print('self.position2d =', end=' ')
        pprint(self.position2d)

    def parse_how(self):
        How = self.xmltree.getroot().findall('How')
        assert len(How) <= 1
        self.how = {}
        if How:
            self.How = How[0]
            #ref = self.How.find('Reference')
            #if ref is not None:
            #    uri = ref.attrib.get('uri')
            #    self.how['reference'] = {'uri': ref}
            #desc = self.How.find('Description')
            #if desc is not None:
            #    self.how['description'] = desc.text
        print('self.how = ', end=' ')
        pprint(self.how)

    def parse_why(self):
        Why = self.xmltree.getroot().findall('Why')
        assert len(Why) <= 1
        self.why = {}
        if Why:
            self.Why = Why[0]
            importance = convert_value(self.Why.attrib.get('importance'))
            expires = convert_value(self.Why.attrib.get('expires'))
            self.why['importance'] = importance
            self.why['expires'] = expires
            desc = self.Why.find('Description')
            desc = desc.text if desc is not None else ''
            self.why['description'] = desc
            inference = self.Why.find('Inference')
            if inference is not None:
                prob = convert_value(inference.attrib.get('probability'))
                rel = convert_value(inference.attrib.get('relation'))
                name = inference.find('Name')
                if name is not None:
                    name = name.text
                concept = inference.find('Concept')
                if concept is not None:
                    concept = concept.text
                    concept = concept.split(';')
                self.why['inference'] = {'probability': prob,
                                         'relation': rel,
                                         'name': name,
                                         'concept': concept}

        print('self.why =', end=' ')
        pprint(self.why)

    def parse_citations(self):
        Citations = self.xmltree.getroot().find('Citations')
        self.Citations = Citations if Citations else None
        self.citations = []
        if self.Citations is not None:
            for cit in Citations:
                if cit.tag == 'EventIVORN':
                    cite = cit.attrib.get('cite')
                    if cite is None:
                        raise ValueError("missing Citations/EventIVORN "
                                         "cite attribute")
                    if cite not in ['followup', 'supersedes', 'retraction']:
                        raise ValueError("incorrect Citations/EventIVORN "
                                         "cite attribute value")
                    self.citations.append((cite, cit.text))
                elif cit.tag == 'Description':
                    self.citations.append(('description', cit.text))
                else:
                    raise ValueError("invalid Citations element")
        print(self.citations)

    def parse_description(self):
        Description = self.xmltree.getroot().find('Description')
        self.Description = Description[0] if Description else None
        self.description = []
        if Description:
            for desc in Description:
                        print(self.Description)

    def parse_reference(self):
        Reference = self.xmltree.getroot().find('Reference')
        if Reference:
            self.Reference = Reference[0]
        print(self.Reference)

    @property
    def skycoord(self):
        """Obtain an astropy SkyCoord from the VO Event"""
        from astropy.coordinates import SkyCoord
        pos = self.position2d
        if not pos:
            raise ValueError("empty coordinates")
        return SkyCoord(ra=pos.ra, dec=pos.dec, unit='deg')


if __name__ == '__main__':
    for fname in sys.argv[1:]:
        event = VOEvent.fromfile(fname)
        event.parse()
        #print(event.skycoord)

        data = xml2python(event.xmltree.getroot(), parse_root=True)
        import os
        with open(os.path.splitext(fname)[0] + '.json', 'w') as fp:
            json.dump(data, fp, indent=2, default=json_serializer_helper)
