# Data inventory

Datasets: 13

### air_pollution_data.csv/air_pollution_data.csv
- Format: CSV | Rows: 23,504 | Dates: 2020-01-12 to 2023-12-05 | Granularity: daily
- Columns: city (object, 0.0% missing); date (object, 0.0% missing); aqi (int64, 0.0% missing); co (float64, 0.0% missing); no (float64, 0.0% missing); no2 (float64, 0.0% missing); o3 (float64, 0.0% missing); so2 (float64, 0.0% missing); pm2_5 (float64, 0.0% missing); pm10 (float64, 0.0% missing); nh3 (float64, 0.0% missing)
- Candidate date: date | Candidate location: city | Unique locations: 26
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: aqi, co, no2, o3, so2, pm2_5, pm10, nh3

### city_day.csv/city_day.csv
- Format: CSV | Rows: 25,555 | Dates: 2015-01-01 to 2020-04-10 | Granularity: daily
- Columns: City (object, 0.0% missing); Date (object, 0.0% missing); PM2.5 (float64, 16.7% missing); PM10 (float64, 41.9% missing); NO (float64, 17.6% missing); NO2 (float64, 12.4% missing); NOx (float64, 15.7% missing); NH3 (float64, 38.3% missing); CO (float64, 7.8% missing); SO2 (float64, 13.7% missing); O3 (float64, 13.7% missing); Benzene (float64, 20.0% missing); Toluene (float64, 29.0% missing); Xylene (float64, 64.2% missing); AQI (float64, 16.6% missing); AQI_Bucket (object, 16.6% missing)
- Candidate date: Date | Candidate location: City | Unique locations: 22
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, CO, SO2, O3, AQI, AQI_Bucket

### india_air_quality_2025_openaq/india_air_quality_2025.csv
- Format: CSV | Rows: 291,005 | Dates: 2024-12-31 to 2025-12-30 | Granularity: daily
- Columns: city (object, 0.0% missing); station (object, 0.0% missing); parameter (object, 0.0% missing); value (float64, 0.0% missing); unit (object, 0.0% missing); date_from (object, 0.0% missing); date_to (object, 0.0% missing); latitude (float64, 0.0% missing); longitude (float64, 0.0% missing); date (object, 0.0% missing); year (int64, 0.0% missing); month (int64, 0.0% missing); month_name (object, 0.0% missing); day (int64, 0.0% missing); aqi_category (object, 82.4% missing)
- Candidate date: date_from | Candidate location: city | Unique locations: 11
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: aqi_category

### indian_cities_aqi_2020_2024/bengaluru_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 4.0% missing); PM10 (float64, 4.1% missing); NO2 (float64, 6.2% missing); NH3 (float64, 6.1% missing); SO2 (float64, 8.3% missing); CO (float64, 4.1% missing); O3 (float64, 7.4% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/chennai_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 4.8% missing); PM10 (float64, 26.4% missing); NO2 (float64, 3.1% missing); NH3 (float64, 28.3% missing); SO2 (float64, 3.2% missing); CO (float64, 2.5% missing); O3 (float64, 3.2% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/delhi_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 0.8% missing); PM10 (float64, 1.1% missing); NO2 (float64, 1.1% missing); NH3 (float64, 1.3% missing); SO2 (float64, 2.4% missing); CO (float64, 1.5% missing); O3 (float64, 1.1% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/gwalior_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 2.0% missing); PM10 (float64, 2.1% missing); NO2 (float64, 2.2% missing); NH3 (float64, 2.3% missing); SO2 (float64, 1.9% missing); CO (float64, 3.0% missing); O3 (float64, 2.0% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/hyderabad_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 1.4% missing); PM10 (float64, 1.6% missing); NO2 (float64, 1.3% missing); NH3 (float64, 1.4% missing); SO2 (float64, 1.0% missing); CO (float64, 1.0% missing); O3 (float64, 2.1% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/jaipur_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 1.2% missing); PM10 (float64, 1.1% missing); NO2 (float64, 1.4% missing); NH3 (float64, 1.8% missing); SO2 (float64, 1.3% missing); CO (float64, 1.4% missing); O3 (float64, 1.5% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/kolkata_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 2.5% missing); PM10 (float64, 2.8% missing); NO2 (float64, 4.7% missing); NH3 (float64, 4.7% missing); SO2 (float64, 2.8% missing); CO (float64, 3.6% missing); O3 (float64, 5.3% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/lucknow_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 0.4% missing); PM10 (float64, 10.8% missing); NO2 (float64, 0.5% missing); NH3 (float64, 10.8% missing); SO2 (float64, 0.4% missing); CO (float64, 1.9% missing); O3 (float64, 0.4% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/mumbai_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 3.9% missing); PM10 (float64, 2.4% missing); NO2 (float64, 2.5% missing); NH3 (float64, 3.1% missing); SO2 (float64, 4.4% missing); CO (float64, 1.1% missing); O3 (float64, 1.9% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

### indian_cities_aqi_2020_2024/visakhapatnam_combined.csv
- Format: CSV | Rows: 1,827 | Dates: 2020-01-01 to 2024-12-31 | Granularity: daily
- Columns: Timestamp (object, 0.0% missing); Location (object, 0.0% missing); PM2.5 (float64, 1.1% missing); PM10 (float64, 0.9% missing); NO2 (float64, 0.7% missing); NH3 (float64, 1.0% missing); SO2 (float64, 0.7% missing); CO (float64, 0.7% missing); O3 (float64, 0.8% missing)
- Candidate date: Timestamp | Candidate location: Location | Unique locations: 1
- Duplicate rows: 0 | Negative numeric values: none
- Pollutant/AQI columns: PM2.5, PM10, NO2, NH3, SO2, CO, O3

## Cross-dataset locations and overlapping date ranges

- ahmedabad: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- aizawl: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-03-11 to 2020-04-10
- amaravati: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- amritsar: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- bengaluru: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- bhopal: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- brajrajnagar: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- chandigarh: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- chennai: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- delhi: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- gurugram: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- guwahati: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- hyderabad: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- jaipur: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- jorapokhar: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- kolkata: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- lucknow: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- mumbai: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- patna: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- shillong: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- talcher: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10
- thiruvananthapuram: air_pollution_data.csv/air_pollution_data.csv <-> city_day.csv/city_day.csv - 2020-01-12 to 2020-04-10

## Data quality summary

- Rows per source: air_pollution_data: 23,504; cities_2020_2024: 18,270; city_day: 25,555; openaq_2025: 3,701
- Clean rows: 62,086; cities: 29; date range: 2015-01-01 to 2025-12-31
- Missing PM2.5 per city: ahmedabad: 19.9%; aizawl: 0.1%; amaravati: 3.2%; amritsar: 6.3%; bengaluru: 5.5%; bhopal: 0.8%; brajrajnagar: 9.1%; chandigarh: 1.3%; chennai: 5.1%; coimbatore: 0.0%; delhi: 0.4%; ernakulam: 0.0%; gurugram: 6.2%; guwahati: 0.1%; gwalior: 2.0%; hyderabad: 3.5%; jaipur: 1.1%; jorapokhar: 38.2%; kochi: 0.0%; kolkata: 3.6%; lucknow: 2.8%; mumbai: 32.3%; nagpur: 0.0%; patna: 12.0%; pune: 0.0%; shillong: 3.9%; talcher: 9.2%; thiruvananthapuram: 2.2%; visakhapatnam: 1.1%
