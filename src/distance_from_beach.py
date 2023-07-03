import bisect
import json
import pathlib
from math import atan2, cos, radians, sin, sqrt


class DistanceFromBeach:

    def __init__(self):
        self.beach_coordinates = json.loads(pathlib.Path('../beach_coordinates.json').read_text())
        self.latitude = [coordinates[0] for coordinates in self.beach_coordinates]

    def calculate(self, coordinates):
        closest_index = find_closest_index(self.latitude, coordinates[0])
        return haversine_distance(coordinates, self.beach_coordinates[closest_index])


def find_closest_index(sorted_list, target):
    # Find the insertion point of the target number in the sorted list
    insertion_point = bisect.bisect_left(sorted_list, target)

    # Determine the index of the closest number in the list
    if insertion_point == 0:
        closest_index = 0
    elif insertion_point == len(sorted_list):
        closest_index = len(sorted_list) - 1
    else:
        left_value = sorted_list[insertion_point - 1]
        right_value = sorted_list[insertion_point]
        closest_index = insertion_point - 1 if target - left_value < right_value - target\
            else insertion_point

    return closest_index


def haversine_distance(point1, point2):
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, (point1[0], point1[1], point2[0], point2[1]))

    # Radius of the Earth in kilometers
    earth_radius_km = 6371.0

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance_meters = int(earth_radius_km * c * 1000)

    return distance_meters


# if __name__ == '__main__':
#     print(DistanceFromBeach().calculate((33.204364, 35.571)))
