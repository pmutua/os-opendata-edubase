#
import csv
import fnmatch
import glob
import os


from fabric import api as fab


PROJECT_DIR = os.path.dirname(__file__)

vrt="""<OGRVRTDataSource>
    <OGRVRTLayer name="codepoint">
        <SrcDataSource>{0}</SrcDataSource>
        <GeometryType>wkbPoint</GeometryType>
        <LayerSRS>EPSG:27700</LayerSRS>
        <GeometryField encoding="PointFromColumns" x="eastings" y="northings"/>
    </OGRVRTLayer>
</OGRVRTDataSource>"""


fields = ['URN',
        'LA (code)',
        'LA (name)',
        'EstablishmentNumber',
        'EstablishmentName',
        'TypeOfEstablishment (name)',
        'EstablishmentStatus (name)',
        'ReasonEstablishmentOpened (name)',
        'OpenDate',
        'ReasonEstablishmentClosed (name)',
        'CloseDate',
        'PhaseOfEducation (name)',
        'StatutoryLowAge',
        'StatutoryHighAge',
        'Boarders (name)',
        'OfficialSixthForm (name)',
        'Gender (name)',
        'ReligiousCharacter (name)',
        'Diocese (name)',
        'AdmissionsPolicy (name)',
        'SchoolCapacity',
        'SpecialClasses (name)',
        'CensusDate',
        'NumberOfPupils',
        'NumberOfBoys',
        'NumberOfGirls',
        'PercentageFSM',
        'TrustSchoolFlag (name)',
        'Trusts (name)',
        'SchoolSponsorFlag (name)',
        'SchoolSponsors (name)',
        'FederationFlag (name)',
        'Federations (name)',
        'UKPRN',
        'FEHEIdentifier',
        'FurtherEducationType (name)',
        'OfstedLastInsp',
        'OfstedSpecialMeasures (name)',
        'LastChangedDate',
        'Street',
        'Locality',
        'Address3',
        'Town',
        'County (name)',
        'Postcode',
        'SchoolWebsite',
        'TelephoneNum',
        'HeadTitle (name)',
        'HeadFirstName',
        'HeadLastName',
        'HeadHonours',
        'HeadPreferredJobTitle',
        'TeenMoth (name)',
        'TeenMothPlaces',
        'CCF (name)',
        'SENPRU (name)',
        'EBD (name)',
        'FTProv (name)',
        'EdByOther (name)',
        'Section41Approved (name)',
        'SEN1 (name)',
        'SEN2 (name)',
        'SEN3 (name)',
        'GOR (name)',
        'AdministrativeWard (name)',
        'ParliamentaryConstituency (name)',
        'UrbanRural (name)',
        'GSSLACode (name)',
        'Easting',
        'Northing',
        'MSOA (name)',
        'LSOA (name)',
        'BoardingEstablishment (name)',
        'PreviousLA (code)',
        'PreviousLA (name)',
        'PreviousEstablishmentNumber']

seed_fields = ['SeedCode',
                'LA Name',
                'Centre Type',
                'School Name',
                'Address 1',
                'Address 2',
                'Address 3',
                'Post code',
                'E-mail',
                'Phone',
                'Primary_school',
                'Secondary',
                'Special',
                'Primary roll',
                'Secondary roll',
                'Special roll',
                'Primary1',
                'Secondary1',
                'Special1',
                'Denomination']

def clean_header(header):
    for h in header:
        h = h.replace(" ", "")
        h = h.replace("(", "_")
        h = h.replace(")", "")
        h = h.replace("-", "")
        yield h



def unzip_codepo():
    with fab.lcd(os.path.join(PROJECT_DIR, 'data')):
        fab.local('unzip codepo_gb.zip')

def unzip_os_local():
    inpath = os.path.join(PROJECT_DIR, 'data')
    with fab.lcd(inpath):
        for f in glob.glob(os.path.join(inpath,'opmplc_essh_*.zip')):
            print f
            fab.local('unzip {0}'.format(f))

def import_shp():

    inpath = os.path.join(PROJECT_DIR, 'data')
    # shp2pgsql does not like the directorynames so we rename them
    for d in glob.glob(os.path.join(inpath, 'OSOpenMapLocal (ESRI Shape File) *')):
        src, dest = d,os.path.join(inpath,d[-2:])
        print src, dest
        os.rename(src, dest)
    first = '''shp2pgsql -d -s 27700:4326 -I -W LATIN1 {0} functional_site | psql -d osopen_data -U osopen'''
    other = '''shp2pgsql -a -s 27700:4326 -W LATIN1 {0} functional_site | psql -d osopen_data -U osopen'''
    template = first
    for root, dirnames, filenames in os.walk(inpath):
        for filename in fnmatch.filter(filenames, '*_FunctionalSite.shp'):
            with fab.lcd(root):
                print os.path.join(root, filename)
                fab.local(template.format(filename))
            template = other





def prepend_headers():
    inpath = os.path.join(PROJECT_DIR, 'data', 'Data', 'CSV')
    outpath = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    header =['postcode',
            'positional_quality_indicator',
            'eastings"',
            'northings',
            'country_code',
            'nhs_regional_ha_code',
            'nhs_ha_code',
            'admin_county_code',
            'admin_district_code',
            'admin_ward_code',]

    if not os.path.exists(outpath):
        os.makedirs(outpath)
    for f in glob.glob(os.path.join(inpath,'*.csv')):
        print f
        with open(os.path.join(outpath, os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                for row in reader:
                    writer.writerow(row)
        csvname=os.path.split(f)[1]
        vofname=csvname.split('.')[0] + '.vrt'
        vrt_name = os.path.join(outpath, vofname)
        with open(vrt_name, 'w') as vrtfile:
            vrtfile.write(vrt.format(vrt_name))

def create_db():
    with fab.settings(warn_only=True):
        fab.local('sudo -u postgres createuser -P osopen')
        fab.local('sudo -u postgres createdb -O osopen osopen_data')
        fab.local('sudo -u postgres psql -d osopen_data -c "CREATE EXTENSION postgis;"')
        fab.local('sudo -u postgres psql -d osopen_data -c "GRANT ALL ON geometry_columns TO PUBLIC;"')
        fab.local('sudo -u postgres psql -d osopen_data -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"')


def ogr2ogr_import_codepoint():
    #XXX this fails for some reason
    first = '''ogr2ogr -nlt PROMOTE_TO_MULTI -progress -nln codepoint -skipfailures -lco PRECISION=no -f PostgreSQL PG:"dbname='osopen_data' host='localhost' port='5432'  user='osopen' password='osopen' " {0}'''
    other = '''ogr2ogr -nlt PROMOTE_TO_MULTI -progress -update -append -nln codepoint -skipfailures -lco PRECISION=no -f PostgreSQL PG:"dbname='osopen_data' host='localhost'  port='5432' user='osopen' password='osopen'" {0}'''
    path = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    template = first
    for f in glob.glob(os.path.join(path,'*.vrt')):
        with fab.lcd(path):
            fab.local(template.format(f))
        template = other

def postcode_sql_import():
    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS postcodes_raw;"')
    fab.local('''psql -d osopen_data -U osopen -c "CREATE TABLE postcodes_raw (
            Postcode character varying(10),
            Positional_quality_indicator character varying(50),
            Eastings character varying(10),
            Northings character varying(10),
            Country_code character varying(50),
            NHS_regional_HA_code character varying(50),
            NHS_HA_code character varying(50),
            Admin_county_code character varying(50),
            Admin_district_code character varying(50),
            Admin_ward_code character varying(50));"
            ''')
    path = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    for f in glob.glob(os.path.join(path,'*.csv')):
        fab.local('''psql -d osopen_data -U osopen -c "\copy postcodes_raw from {0} WITH (FORMAT CSV, HEADER, DELIMITER ',');"'''.format(f))
    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS postcodes;"')
    fab.local('''psql -d osopen_data -U osopen -c "SELECT
        postcode,
        ST_TRANSFORM(ST_GEOMFROMEWKT('SRID=27700;POINT(' || eastings || ' ' || northings || ')'), 4326)::GEOGRAPHY(Point, 4326) AS location
        INTO postcodes FROM postcodes_raw;"''')
    fab.local('psql -d osopen_data -U osopen -c "CREATE INDEX postcodes_geog_idx ON postcodes USING GIST(location);"')
    fab.local('psql -d osopen_data -U osopen -c "ALTER TABLE postcodes ADD PRIMARY KEY (Postcode);"')
    #fab.local('psql -d osopen_data -U osopen -c "DROP TABLE postcodes_raw;"')




def edubase_import():
    header = list(clean_header(fields))
    inpath = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(inpath,'edubasealldata*.csv')):
         with open(os.path.join(inpath, 'processed_csv_' + os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                reader.next()
                for row in reader:
                    writer.writerow(row)

def edubase_sql_import():
    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS edubase_raw;"')
    cols = ['{0} character varying(500)'.format(f) for f in (clean_header(fields))]
    fab.local('''psql -d osopen_data -U osopen -c "CREATE TABLE edubase_raw (
              {0});"'''.format(', '.join(cols)))
    path = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(path,'processed_csv_edubasealldata*.csv')):
        fab.local('''psql -d osopen_data -U osopen -c "\copy edubase_raw from
                  {0}
                  WITH (FORMAT CSV, HEADER, ENCODING 'LATIN1', DELIMITER ',');"'''.format(f))
    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS edubase;"')
    fab.local('''psql -d osopen_data -U osopen -c "SELECT
        edubase_raw.*,
        ST_TRANSFORM(ST_GEOMFROMEWKT('SRID=27700;POINT(' || easting || ' ' || northing || ')'), 4326)::GEOGRAPHY(Point, 4326) AS location
        INTO edubase FROM edubase_raw;"''')
    fab.local('psql -d osopen_data -U osopen -c "CREATE INDEX edubase_location_geog_idx ON edubase USING GIST(location);"')
    fab.local('psql -d osopen_data -U osopen -c "ALTER TABLE edubase ADD PRIMARY KEY (urn);"')


def seed_import():
    header = list(clean_header(seed_fields))
    inpath = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(inpath,'seeddata*.csv')):
         with open(os.path.join(inpath, 'processed_csv_' + os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                reader.next()
                for row in reader:
                    writer.writerow(row)

def seed_sql_import():
    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS seed_raw;"')
    cols = ['{0} character varying(200)'.format(f) for f in (clean_header(seed_fields))]
    fab.local('''psql -d osopen_data -U osopen -c "CREATE TABLE seed_raw (
              {0});"'''.format(', '.join(cols)))
    path = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(path,'processed_csv_seeddata*.csv')):
        fab.local('''psql -d osopen_data -U osopen -c "\copy seed_raw from
                  {0}
                  WITH (FORMAT CSV, HEADER, DELIMITER ',');"'''.format(f))
    fab.local('''psql -d osopen_data -U osopen -c " SELECT seed_raw.*, postcodes.location as location
                FROM postcodes INNER JOIN seed_raw
                ON replace(postcodes.postcode, ' ', '')=replace(seed_raw.postcode, ' ','')
                INTO seed_data;"''')
    fab.local('psql -d osopen_data -U osopen -c "CREATE INDEX seed_location_geog_idx ON seed_data USING GIST(location);"')
    fab.local('psql -d osopen_data -U osopen -c "ALTER TABLE seed_data ADD COLUMN id SERIAL PRIMARY KEY;"')


def combine_edubase_seed():

    fab.local('psql -d osopen_data -U osopen -c "DROP TABLE IF EXISTS schools;"')
    create_sql = """
    CREATE TABLE schools
    (
      source character varying(8),
      uid integer,
      local_authority character varying(255),
      schoolname character varying(255),
      postcode character varying(8),
      street character varying(255),
      locality character varying(255),
      town character varying(255),
      phone character varying(32),
      phaseofeducation character varying(32),
      website character varying(255),
      location geometry(Point,4326),
      id serial NOT NULL,
      CONSTRAINT school_id_pk PRIMARY KEY (id)
    );

    ALTER TABLE schools
      OWNER TO osopen;

    CREATE INDEX schools_geog_idx
      ON schools
      USING gist
      (location);
    """

    fab.local('psql -d osopen_data -U osopen -c "{0}"'.format(create_sql))


    combine_schools_sql = """
    INSERT INTO schools (source, uid, local_authority,
        schoolname, postcode, street, locality, town,
        phone, phaseofeducation, website, location)
    SELECT
      'SEED' as source,
      seed_data.seedcode::integer as uid,
      seed_data.laname as local_authority,
      seed_data.schoolname,
      trim(seed_data.postcode),
      seed_data.address1 as street,
      seed_data.address2 as locality,
      replace(seed_data.address3, ' - ', '') as town,
      seed_data.phone,
      replace(replace(seed_data.primary_school, ' ', ''), '-','') ||
      replace(replace(seed_data.secondary, ' ', ''), '-','')
      as phaseofeducation,
      '' as website,
      seed_data.location::geometry
    FROM
      public.seed_data
    union
    SELECT
      'EDUBASE' as source,
      edubase.urn::integer,
      edubase.la_name,
      edubase.establishmentname,
      trim(edubase.postcode),
      edubase.street,
      edubase.locality,
      edubase.town,
      edubase.telephonenum,
      edubase.phaseofeducation_name,
      edubase.schoolwebsite,
      edubase.location::geometry
    FROM
      public.edubase
    """
    fab.local('psql -d osopen_data -U osopen -c "{0}"'.format(combine_schools_sql))

