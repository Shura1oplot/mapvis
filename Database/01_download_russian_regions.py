#!/usr/bin/env python3

import sys
import requests


def main(argv=sys.argv):
    objects = {}

    query = """
        [out:json];
        relation(60189)->.russia;
        rel(r.russia)["admin_level"="3"]["boundary"="administrative"];
        out tags;
    """

    response = requests.post("http://overpass-api.de/api/interpreter",
                             data={"data": query})
    response.raise_for_status()
    data = response.json()

    for elem in data["elements"]:
        objects[elem["tags"]["name"]] = {
            "admin_level": 3,
            "id": elem["id"]}

    count = len(objects)
    print("Federal districts:", count)

    for obj in list(objects.values()):
        query = f"""
            [out:json];
            relation({obj["id"]})->.federal_district;
            rel(r.federal_district)["admin_level"="4"]["boundary"="administrative"];
            out tags;
        """

        response = requests.post("http://overpass-api.de/api/interpreter",
                                 data={"data": query})
        response.raise_for_status()
        data = response.json()

        for elem in data["elements"]:
            objects[elem["tags"]["name"]] = {
                "admin_level": 4,
                "id": elem["id"]}

    print("Oblasts:", len(objects) - count)
    count = len(objects)

    # Новые территории
    # Луганская, Донецкая, Запорожская, Херсонская области
    # 3795586 - Крым (по данным OSM уже в составе России)
    query = """
        [out:json];
        relation(id:71971,71973,71980,71022);
        out tags;
    """

    response = requests.post("http://overpass-api.de/api/interpreter",
                             data={"data": query})
    response.raise_for_status()
    data = response.json()

    for elem in data["elements"]:
        objects[elem["tags"]["name:ru"]] = {
            "admin_level": 4,
            "id": elem["id"],
            "new_regions": True}

    print("New regions:", len(objects) - count)

    print("Downloading geometry data")

    ids = ",".join(str(obj["id"]) for obj in objects.values())
    query = f"""
        [out:json];
        relation(id:{ids});
        out geom;
    """

    response = requests.post("http://overpass-api.de/api/interpreter",
                             data={"data": query})
    response.raise_for_status()

    osm = response.text

    with open("russian_regions_osm.json", "w", encoding="utf-8") as fp:
        fp.write(osm)



if __name__ == "__main__":
    sys.exit(main())
