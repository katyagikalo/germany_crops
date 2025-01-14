import requests
import geopandas as gpd
import os
from shapely.geometry import Polygon, MultiPolygon
import pandas as pd


def fetch_city_boundary(city_name, output_dir="shapefiles"):
    overpass_url = "https://overpass-api.de/api/interpreter"

    query = f"""
    [out:json];
    area["name"="Deutschland"]->.searchArea;
    relation["boundary"="administrative"]["name"="{city_name}"](area.searchArea);
    out body;
    >;
    out skel qt;
    """

    try:
        response = requests.post(overpass_url, data={"data": query})
        response.raise_for_status()

        data = response.json()
        if "elements" not in data or not data["elements"]:
            print(f"No boundary data found for {city_name}.")
            if "Landkreis" in city_name:
                city_name = city_name.replace("Landkreis ", "")
                if not fetch_city_boundary(city_name, output_dir):
                    city_name = "Kreis " + city_name
                    return fetch_city_boundary(city_name, output_dir)
            else:
                return None

        nodes = {element["id"]: (element["lon"], element["lat"]) for element in data["elements"] if
                 element["type"] == "node"}
        ways = [element for element in data["elements"] if element["type"] == "way"]

        polygons = []
        for way in ways:
            coords = [nodes[node_id] for node_id in way["nodes"] if node_id in nodes]
            if len(coords) > 2:
                polygons.append(Polygon(coords))

        if not polygons:
            print("No valid polygons found.")
            return None

        geometry = MultiPolygon(polygons) if len(polygons) > 1 else polygons[0]

        gdf = gpd.GeoDataFrame([{"name": city_name, "geometry": geometry}], crs="EPSG:4326")

        output_dir_dis = os.path.join(output_dir, city_name)
        os.makedirs(output_dir_dis, exist_ok=True)
        shapefile_path = os.path.join(output_dir_dis, f"{city_name}_boundary.shp")
        gdf.to_file(shapefile_path)

        return shapefile_path

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return None
    except Exception as e:
        print(f"Processing error: {e}")
        return None


def extract_unique_districts(csv_path, district_column):
    try:
        df = pd.read_csv(csv_path)

        districts = (
            df[district_column]
            .dropna()
            .str.replace(", kreisfreie Stadt", "", regex=False)
            .apply(lambda x: f"Landkreis {x.replace(', Landkreis', '').strip()}" if ", Landkreis" in x else x)
        )

        unique_districts = sorted(districts.unique())

        print(f"Unique districts extracted: {len(unique_districts)} found.")
        return unique_districts
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return None


if __name__ == "__main__":
    csv_path = "district_data.csv"
    district_column = "district"

    districts = extract_unique_districts(csv_path, district_column)
    # print(districts)

    for district in districts:
        fetch_city_boundary(district)
