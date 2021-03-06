#
import csv
import fnmatch
import glob
import os
import urllib

from fabric import api as fab

PROJECT_DIR = os.path.dirname(__file__)
DB_NAME = 'osopen_data'
DB_USER = 'osopen'


vrt = """<OGRVRTDataSource>
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
        for f in glob.glob(os.path.join(inpath, 'opmplc_essh_*.zip')):
            print f
            with fab.settings(warn_only=True):
                fab.local('unzip {0} *FunctionalSite.*'.format(f))


def import_shp():
    inpath = os.path.join(PROJECT_DIR, 'data')
    # shp2pgsql does not like the directorynames so we rename them
    for d in glob.glob(os.path.join(inpath, 'OSOpenMapLocal (ESRI Shape File) *')):
        src, dest = d, os.path.join(inpath, d[-2:])
        try:
            os.rename(src, dest)
        except OSError:
            pass
    template = '''shp2pgsql -d -s 27700:4326 -I -W LATIN1 {0} functional_site | psql -d {1} -U {2} -h localhost'''

    create_sql = """
    DROP TABLE IF EXISTS education_site CASCADE;
    DROP TABLE IF EXISTS functional_site CASCADE;

    CREATE TABLE education_site
    (
      id serial NOT NULL,
      gid integer NOT NULL,
      grid_ref character varying(2) NOT NULL,
      distname character varying(120),
      sitetheme character varying(21),
      classifica character varying(90),
      featcode numeric,
      geom geometry(MultiPolygon,4326),
      CONSTRAINT education_site_pkey PRIMARY KEY (id),
      CONSTRAINT education_site_gid_grid_ref_key UNIQUE (gid, grid_ref)
    );

    ALTER TABLE education_site
    OWNER TO osopen;

    CREATE INDEX education_site_geom_gist
      ON education_site
      USING gist
      (geom);
    """
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, create_sql))

    insert_sql = """
    INSERT INTO education_site
    (gid, grid_ref, distname, sitetheme, classifica, featcode, geom)
    SELECT
        gid,
        '{0}' as grid_ref,
        distname,
        sitetheme,
        classifica,
        featcode,
        geom
    FROM functional_site
    WHERE
        sitetheme = 'Education';
    """

    for root, dirnames, filenames in os.walk(inpath):
        for filename in fnmatch.filter(filenames, '*_FunctionalSite.shp'):
            with fab.lcd(root):
                print filename
                gridref =  filename[:2]
                fab.local(template.format(filename, DB_NAME, DB_USER))
                sql = insert_sql.format(gridref)
                fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, sql))



def import_osm():
    imppath = os.path.join(PROJECT_DIR, 'data', 'osm')

    with fab.lcd(imppath):
        cmd = ('ogr2ogr -f PostgreSQL "PG:dbname={0} user={1} host=localhost" {2}/schools.osm '
               '-lco COLUMN_TYPES=other_tags=hstore  '
               '-overwrite').format(DB_NAME, DB_USER, imppath)
        fab.local(cmd)
        # college
        cmd = ('ogr2ogr -f PostgreSQL "PG:dbname={0} user={1} host=localhost" {2}/colleges.osm '
               '-lco COLUMN_TYPES=other_tags=hstore '
               '-append').format(DB_NAME, DB_USER, imppath)
        fab.local(cmd)

def prepend_headers():
    inpath = os.path.join(PROJECT_DIR, 'data', 'Data', 'CSV')
    outpath = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    header = ['postcode',
              'positional_quality_indicator',
              'eastings"',
              'northings',
              'country_code',
              'nhs_regional_ha_code',
              'nhs_ha_code',
              'admin_county_code',
              'admin_district_code',
              'admin_ward_code', ]

    if not os.path.exists(outpath):
        os.makedirs(outpath)
    for f in glob.glob(os.path.join(inpath, '*.csv')):
        print f
        with open(os.path.join(outpath, os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                for row in reader:
                    writer.writerow(row)
        csvname = os.path.split(f)[1]
        vofname = csvname.split('.')[0] + '.vrt'
        vrt_name = os.path.join(outpath, vofname)
        with open(vrt_name, 'w') as vrtfile:
            vrtfile.write(vrt.format(vrt_name))


def create_db():
    """
    This should already have been doe by the install script.
    """
    with fab.settings(warn_only=True):
        fab.local('sudo -u postgres createuser -P {0}'.format(DB_USER))
        fab.local('sudo -u postgres createdb -O {0} {1}'.format(DB_USER, DB_NAME))
        fab.local('sudo -u postgres psql -d {0} -c "CREATE EXTENSION postgis;"'.format(DB_NAME))
        fab.local(
            'sudo -u postgres psql -d {0} -c "GRANT ALL ON geometry_columns TO PUBLIC;"'.format(DB_NAME))
        fab.local(
            'sudo -u postgres psql -d {0} -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"'.format(DB_NAME))
        fab.local('sudo -u postgres psql -d {0} -c "CREATE EXTENSION hstore;"'.format(DB_NAME))


def ogr2ogr_import_codepoint():
    # XXX this fails for some reason
    first = '''ogr2ogr -nlt PROMOTE_TO_MULTI -progress -nln codepoint -skipfailures -lco PRECISION=no -f PostgreSQL PG:"dbname='osopen_data' host='localhost' port='5432'  user='osopen'" {0}'''
    other = '''ogr2ogr -nlt PROMOTE_TO_MULTI -progress -update -append -nln codepoint -skipfailures -lco PRECISION=no -f PostgreSQL PG:"dbname='osopen_data' host='localhost'  port='5432' user='osopen'" {0}'''
    path = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    template = first
    for f in glob.glob(os.path.join(path, '*.vrt')):
        with fab.lcd(path):
            fab.local(template.format(f))
        template = other


def postcode_sql_import():
    fab.local(
        'psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS postcodes_raw;"'.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "CREATE TABLE postcodes_raw (
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
            '''.format(DB_NAME, DB_USER))
    path = os.path.join(PROJECT_DIR, 'data', 'Data', 'processed_csv')
    for f in glob.glob(os.path.join(path, '*.csv')):
        fab.local('''psql -d {0} -U {1} -h localhost -c "\copy postcodes_raw
                  from {2} WITH (FORMAT CSV, HEADER, DELIMITER ',');"'''
                  .format(DB_NAME, DB_USER, f))
    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS postcodes;"'.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "SELECT
        postcode,
        ST_TRANSFORM(ST_GEOMFROMEWKT('SRID=27700;POINT(' || eastings || ' ' || northings || ')'), 4326)::GEOGRAPHY(Point, 4326) AS location
        INTO postcodes FROM postcodes_raw;"'''.format(DB_NAME, DB_USER))
    fab.local(
        'psql -d {0} -U {1} -h localhost -c "CREATE INDEX postcodes_geog_idx ON postcodes USING GIST(location);"'.format(DB_NAME, DB_USER))
    fab.local(
        'psql -d {0} -U {1} -h localhost -c "ALTER TABLE postcodes ADD PRIMARY KEY (Postcode);"'.format(DB_NAME, DB_USER))
    #fab.local('psql -d osopen_data -U osopen -c "DROP TABLE postcodes_raw;"')


def edubase_import():
    header = list(clean_header(fields))
    inpath = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(inpath, 'edubasealldata*.csv')):
        with open(os.path.join(inpath, 'processed_csv_' + os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                reader.next()
                for row in reader:
                    writer.writerow(row)


def edubase_sql_import():
    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS edubase_raw;"'.format(DB_NAME, DB_USER))
    cols = ['{0} character varying(500)'.format(f) for f in (clean_header(fields))]
    fab.local('''psql -d {0} -U {1} -h localhost -c "CREATE TABLE edubase_raw (
              {2});"'''.format(DB_NAME, DB_USER, ', '.join(cols)))
    path = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(path, 'processed_csv_edubasealldata*.csv')):
        fab.local('''psql -d {0} -U {1} -h localhost -c "\copy edubase_raw from
                  {2}
                  WITH (FORMAT CSV, HEADER, ENCODING 'LATIN1', DELIMITER ',');"'''
                  .format(DB_NAME, DB_USER, f))
    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS edubase;"'.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "SELECT
        edubase_raw.*,
        ST_TRANSFORM(ST_GEOMFROMEWKT(
            'SRID=27700;POINT(' || easting || ' ' || northing || ')'), 4326
            )::GEOGRAPHY(Point, 4326) AS location
        INTO edubase FROM edubase_raw;"'''.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "CREATE INDEX edubase_location_geog_idx
        ON edubase USING GIST(location);"'''
        .format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "ALTER TABLE edubase
        ADD PRIMARY KEY (urn);"'''.format(DB_NAME, DB_USER))


def seed_import():
    header = list(clean_header(seed_fields))
    inpath = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(inpath, 'seeddata*.csv')):
        with open(os.path.join(inpath, 'processed_csv_' + os.path.split(f)[1]), 'w') as outfile:
            with open(f, 'r') as infile:
                writer = csv.writer(outfile)
                writer.writerow(header)
                reader = csv.reader(infile)
                reader.next()
                for row in reader:
                    writer.writerow(row)


def seed_sql_import():
    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS seed_raw;"'.format(DB_NAME, DB_USER))
    cols = ['{0} character varying(200)'.format(f) for f in (clean_header(seed_fields))]
    fab.local('''psql -d {0} -U {1} -h localhost -c "CREATE TABLE seed_raw (
              {2});"'''.format(DB_NAME, DB_USER, ', '.join(cols)))
    path = os.path.join(PROJECT_DIR, 'data')
    for f in glob.glob(os.path.join(path, 'processed_csv_seeddata*.csv')):
        fab.local('''psql -d {0} -U {1} -h localhost -c "\copy seed_raw from
                  {2}
                  WITH (FORMAT CSV, HEADER, DELIMITER ',');"'''.format(DB_NAME, DB_USER, f))
    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS seed_data;"'.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c " SELECT seed_raw.*, postcodes.location as location
                INTO seed_data
                FROM postcodes INNER JOIN seed_raw
                ON replace(postcodes.postcode, ' ', '')=replace(seed_raw.postcode, ' ','')
                ;"'''.format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "CREATE INDEX seed_location_geog_idx
        ON seed_data USING GIST(location);"'''
        .format(DB_NAME, DB_USER))
    fab.local('''psql -d {0} -U {1} -h localhost -c "ALTER TABLE seed_data
        ADD COLUMN id SERIAL PRIMARY KEY;"'''
        .format(DB_NAME, DB_USER))


def combine_edubase_seed():

    fab.local('psql -d {0} -U {1} -h localhost -c "DROP TABLE IF EXISTS school CASCADE;"'.format(DB_NAME, DB_USER))
    create_sql = """
    CREATE TABLE school
    (
      source character varying(8),
      uid integer,
      local_authority character varying(255),
      schoolname character varying(255),
      status_name character varying(32),
      postcode character varying(8),
      street character varying(255),
      locality character varying(255),
      town character varying(255),
      phone character varying(32),
      phaseofeducation character varying(32),
      website character varying(255),
      location geometry(Point,4326),
      id serial NOT NULL,
      PRIMARY KEY (id)
    );

    ALTER TABLE school
      OWNER TO osopen;

    CREATE INDEX school_geog_idx
      ON school
      USING gist
      (location);
    """

    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, create_sql))

    combine_schools_sql = """
    INSERT INTO school (source, uid, local_authority,
        schoolname, status_name, postcode, street, locality, town,
        phone, phaseofeducation, website, location)
    SELECT
      'SEED' as source,
      seed_data.seedcode::integer as uid,
      seed_data.laname as local_authority,
      seed_data.schoolname,
      'open' as status_name,
      trim(seed_data.postcode),
      seed_data.address1 as street,
      seed_data.address2 as locality,
      replace(seed_data.address3, ' - ', '') as town,
      seed_data.phone,
      trim(replace(replace(seed_data.primary_school, ' ', ''), '-','') || ' ' ||
      replace(replace(seed_data.secondary, ' ', ''), '-',''))
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
      edubase.establishmentstatus_name,
      trim(edubase.postcode),
      edubase.street,
      edubase.locality,
      edubase.town,
      edubase.telephonenum,
      edubase.phaseofeducation_name,
      edubase.schoolwebsite,
      edubase.location::geometry
    FROM
      public.edubase;
    """
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, combine_schools_sql))


def get_osm_schooldata():
    """
    GET /api/0.6/map?bbox=left,bottom,right,top

    where:

    left is the longitude of the left (westernmost) side of the bounding box, or minlon.
    bottom is the latitude of the bottom (southernmost) side of the bounding box, or minlat.
    right is the longitude of the right (easternmost) side of the bounding box, or maxlon.
    top is the latitude of the top (northernmost) side of the bounding box, or maxlat.

    Bounding Box:
    NE 55.811741, 1.76896
    SW 49.871159, -6.37988
    """

    url = 'http://www.overpass-api.de/api/xapi_meta?*[amenity=school][bbox=-6,50,2,61]'
    # Make data queries to jXAPI
    schoolxml = urllib.urlopen(url).read()
    schools_file = open(os.path.join(PROJECT_DIR, 'data', 'osm', 'schools.osm'), 'w')
    schools_file.write(schoolxml)
    schools_file.close()
    url = 'http://www.overpass-api.de/api/xapi_meta?*[amenity=college][bbox=-6,50,2,61]'
    # Make data queries to jXAPI
    collegexml = urllib.urlopen(url).read()
    college_file = open(os.path.join(PROJECT_DIR, 'data', 'osm', 'colleges.osm'), 'w')
    college_file.write(collegexml)
    college_file.close()

def get_sites_near_schools():
    """
    Sites nearby a school:
    all sites correlated with school in ~ 150m
    -> http://stackoverflow.com/questions/8464666/distance-between-2-points-in-postgis-in-srid-4326-in-metres
    """

    sql_site_near_school = '''
    DROP TABLE IF EXISTS education_site_near_school CASCADE;

    SELECT DISTINCT education_site.id as site_id, school.id as school_id
    INTO education_site_near_school
    FROM education_site, school
    WHERE ST_DWithin(education_site.geom, school.location, 0.0014)
    AND school.status_name ILIKE 'open%';

    ALTER TABLE education_site_near_school
    ADD COLUMN id serial PRIMARY KEY;

    ALTER TABLE education_site_near_school
        ADD UNIQUE (site_id, school_id);

    ALTER TABLE education_site_near_school
        ADD CONSTRAINT fk_education_site
        FOREIGN KEY (site_id)
        REFERENCES education_site (id);

    ALTER TABLE education_site_near_school
        ADD CONSTRAINT fk_school
        FOREIGN KEY (school_id)
        REFERENCES school (id);
    '''
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, sql_site_near_school))


def get_sites_overlapping_osm():
    sql_overlapping = '''
    DROP TABLE IF EXISTS education_site_overlaps_osm CASCADE;

    SELECT DISTINCT education_site.id as site_id, multipolygons.ogc_fid
        INTO education_site_overlaps_osm
        FROM education_site, multipolygons
        WHERE ST_Intersects(education_site.geom, multipolygons.wkb_geometry);

    ALTER TABLE education_site_overlaps_osm
        ADD COLUMN id serial PRIMARY KEY;

    ALTER TABLE education_site_overlaps_osm
        ADD UNIQUE (site_id, ogc_fid);

    ALTER TABLE education_site_overlaps_osm
        ADD CONSTRAINT fk_education_site
        FOREIGN KEY (site_id)
        REFERENCES education_site (id);

    ALTER TABLE education_site_overlaps_osm
        ADD CONSTRAINT fk_osm_multipolygon
        FOREIGN KEY (ogc_fid)
        REFERENCES multipolygons (ogc_fid);

    '''
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, sql_overlapping))

def post_import():
    post_sql = """
    DROP TABLE IF EXISTS functional_site CASCADE;
    DROP TABLE IF EXISTS postcodes_raw CASCADE;
    DROP TABLE IF EXISTS edubase_raw CASCADE;
    DROP TABLE IF EXISTS seed_raw CASCADE;
    DROP TABLE IF EXISTS edubase CASCADE;
    DROP TABLE IF EXISTS seed_data CASCADE;
    DROP TABLE IF EXISTS functional_site_near_school CASCADE;
    DROP TABLE IF EXISTS functional_site_overlaps_osm CASCADE;
    """
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, post_sql))
    fab.local('psql -d {0} -U {1} -h localhost -c "VACUUM ANALYZE;"'.format(DB_NAME, DB_USER))

def create_views():
    sql = """
    CREATE OR REPLACE VIEW importable_site
    AS
    SELECT DISTINCT education_site.*
    FROM education_site
    INNER JOIN education_site_near_school
    ON education_site.id = education_site_near_school.site_id;

    CREATE OR REPLACE VIEW importable_site_no_osm
    AS
    SELECT DISTINCT education_site.*
    FROM education_site
    INNER JOIN education_site_near_school
    ON education_site.id = education_site_near_school.site_id
    WHERE education_site.id NOT IN (SELECT site_id FROM education_site_overlaps_osm)
    AND education_site.id NOT IN (SELECT site_id FROM schools_importlog)
    AND education_site.id NOT IN (SELECT site_id FROM schools_sitecomment);

    """
    fab.local('psql -d {0} -U {1} -h localhost -c "{2}"'.format(DB_NAME, DB_USER, sql))

def get_size(filename):
    st = os.stat(filename)
    return st.st_size

def update_osm():
    get_osm_schooldata()
    if (get_size(os.path.join(PROJECT_DIR, 'data', 'osm', 'schools.osm')) > 50000000 and
        get_size(os.path.join(PROJECT_DIR, 'data', 'osm', 'colleges.osm')) > 2000000):
        import_osm()
        get_sites_overlapping_osm()
        create_views()

def update_seed_edubase():
    edubase_import()
    edubase_sql_import()
    seed_import()
    seed_sql_import()
    combine_edubase_seed()
    post_import()


def init_db():
    unzip_codepo()
    prepend_headers()
    unzip_os_local()
    get_osm_schooldata()
    postcode_sql_import()
    edubase_import()
    edubase_sql_import()
    seed_import()
    seed_sql_import()
    combine_edubase_seed()
    import_shp()
    import_osm()
    get_sites_overlapping_osm()
    get_sites_near_schools()
    create_views()
    post_import()
