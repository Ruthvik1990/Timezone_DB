import requests
import datetime
import json
import time
import mysql.connector

# Declaring the API Key
TIMEZONE_API_KEY = "YHF4HJOPTRU2"
TIMEZONE_API_BASE_URL = "http://api.timezonedb.com/v2"

DATABASE_CONNECTION_PARAMS = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "MySQL@1212",
    "database": "timezone_db"
}

class TimezoneApiDataProcessing:
    def __init__(self):
        self.conn = mysql.connector.connect(**DATABASE_CONNECTION_PARAMS)
        self.cursor = self.conn.cursor()

    def get_timezone_list(self):

    # Fetching list of the timezones from the TimezoneDB API.

        url = f"{TIMEZONE_API_BASE_URL}/list-time-zone"
        params = {
            "key": TIMEZONE_API_KEY,
            "format": "json"
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            timezones = response.json()["zones"]
            print("Timezone list retrieved successfully.")
            return timezones
        except requests.RequestException as e:
            self.log_error(e)

    def add_data_to_timezones_table(self, timezones):
        
        # Adding records into TZDB_TIMEZONES table with data from the API.

        # Deleting existing data in TZDB_TIMEZONES
        self.cursor.execute("DELETE FROM TZDB_TIMEZONES")
        print("Existing data deleted from TZDB_TIMEZONES table.")

        # Inserting new data into the table
        for timezone in timezones:
            country_code, country_name, zone_name, gmt_offset = timezone["countryCode"], timezone["countryName"], \
            timezone[
                "zoneName"], timezone["gmtOffset"]
            import_date = datetime.datetime.now()
            self.cursor.execute(
                "INSERT INTO TZDB_TIMEZONES (COUNTRYCODE, COUNTRYNAME, ZONENAME, GMTOFFSET, IMPORT_DATE) VALUES (%s, %s, %s, %s, %s)",
                (country_code, country_name, zone_name, gmt_offset, import_date))
        self.conn.commit()
        print("Timezones populated into TZDB_TIMEZONES table successfully.")

    def log_error(self, error_message):

        # Loging errors into the TZDB_ERROR_LOG table; adding message.

        error_date = datetime.datetime.now()
        self.cursor.execute("INSERT INTO TZDB_ERROR_LOG (ERROR_DATE, ERROR_MESSAGE) VALUES (%s, %s)",
                       (error_date, str(error_message)))

        self.conn.commit()

    def get_timezone_details(self, tz):
        
        # Fetches details for the specified ZONENAME from the TimezoneDB API.

        url = f"{TIMEZONE_API_BASE_URL}/get-time-zone"
        params = {
            "key": TIMEZONE_API_KEY,
            "format": "json",
            "by": "zone",
            "zone": tz['zoneName']
        }
        try:
            response = requests.get(url, params=params)
            detailsresp = response.json()
            return detailsresp
        except requests.RequestException as e:
            self.log_error(e)
        except Exception as e:
            self.log_error(f"Error for {tz['zoneName']}, {e}")

    def add_data_to_zone_details_stage(self, details):

        # Adding records into staging table TZDB_ZONE_DETAILS_STAGE.

        country_code = details["countryCode"]
        country_name = details["countryName"]
        zone_name = details["zoneName"]
        gmt_offset = details["gmtOffset"]
        dst = details["dst"]
        zone_start = details["zoneStart"]
        zone_end = details["zoneEnd"]
        import_date = datetime.datetime.now()

        query_to_execute = """
            INSERT INTO TZDB_ZONE_DETAILS_STAGE 
            (COUNTRYCODE, COUNTRYNAME, ZONENAME, GMTOFFSET, DST, ZONESTART, ZONEEND, IMPORT_DATE) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            COUNTRYCODE = VALUES(COUNTRYCODE),
            COUNTRYNAME = VALUES(COUNTRYNAME),
            GMTOFFSET = VALUES(GMTOFFSET),
            DST = VALUES(DST),
            IMPORT_DATE = VALUES(IMPORT_DATE)
        """
        self.cursor.execute(query_to_execute,
                       (country_code, country_name, zone_name, gmt_offset, dst, zone_start, zone_end, import_date))
        print(f"Details for timezone {zone_name} staged successfully.")

    def move_data_from_stage_to_main(self):
        
        # Moving data from staging table TZDB_ZONE_DETAILS_STAGE to table TZDB_ZONE_DETAILS.
        # Deleting records from staging table after moving to TZDB_ZONE_DETAILS.

        insert_query = """
        INSERT INTO TZDB_ZONE_DETAILS
        (COUNTRYCODE, COUNTRYNAME, ZONENAME, GMTOFFSET, DST, ZONESTART, ZONEEND, IMPORT_DATE)
        SELECT 
            COUNTRYCODE, COUNTRYNAME, ZONENAME, GMTOFFSET, DST, ZONESTART, ZONEEND, IMPORT_DATE
        FROM 
            TZDB_ZONE_DETAILS_STAGE
        ON DUPLICATE KEY UPDATE
            COUNTRYCODE = VALUES(COUNTRYCODE),
            COUNTRYNAME = VALUES(COUNTRYNAME),
            GMTOFFSET = VALUES(GMTOFFSET),
            DST = VALUES(DST),
            IMPORT_DATE = VALUES(IMPORT_DATE);
        """

        try:
            self.cursor.execute(insert_query)
            print("DATA MOVED FROM STAGING TABLE TO MAIN TABLE SUCCESSFULLY.")

            self.cursor.execute("TRUNCATE TABLE TZDB_ZONE_DETAILS_STAGE")
            print("REMOVED DATA FROM STAGING TABLE SUCCESSFULLY")
        except Exception as e:
            print("An error occurred:", e)


def main():
    time_zone_api_data = TimezoneApiDataProcessing()
    try:
        timezones = time_zone_api_data.get_timezone_list()

        time_zone_api_data.add_data_to_timezones_table(timezones)
        print("Updating the TZDB_ZONE_DETAILS_STAGE...")
        for tz in timezones:
            time.sleep(2)
            details = time_zone_api_data.get_timezone_details(tz)
            if details["zoneEnd"] is None:
                continue
            time_zone_api_data.add_data_to_zone_details_stage(details)
        time_zone_api_data.conn.commit()
        time_zone_api_data.move_data_from_stage_to_main()

        time_zone_api_data.conn.commit()
        time_zone_api_data.conn.close()
    except Exception as e:
        time_zone_api_data.log_error(e)


if __name__ == "__main__":
    main()

#EOF