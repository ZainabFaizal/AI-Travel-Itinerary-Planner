# itinerary_manager.py

import json
from destination import Destination
import os

class ItineraryManager:
    def __init__(self, filename="data/destinations.json"):
        self.destinations = []
        self.filename = filename
        self.load_from_file()

    def add_destination(self, destination_data):
        try:
            # Basic validation before creating object
            city = destination_data['city'].strip()
            country = destination_data['country'].strip()
            start_date = destination_data['start_date']
            end_date = destination_data['end_date']
            budget = float(destination_data['budget'])
            activities = [a.strip() for a in destination_data['activities']]

            # Further validation using Destination's internal methods
            temp_dest = Destination(city, country, start_date, end_date, budget, activities)
            if not temp_dest._validate_date(start_date) or \
               not temp_dest._validate_date(end_date) or \
               not temp_dest._validate_budget(budget) or \
               not temp_dest._validate_activities(activities):
                print("Validation failed for one or more fields. Destination not added.")
                return False

            self.destinations.append(temp_dest)
            print(f"Destination '{city}, {country}' added successfully.")
            return True
        except ValueError:
            print("Invalid input for budget or activities. Please try again.")
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def remove_destination(self, city_name):
        initial_len = len(self.destinations)
        self.destinations = [d for d in self.destinations if d.city.lower() != city_name.lower()]
        if len(self.destinations) < initial_len:
            print(f"Destination '{city_name}' removed.")
            return True
        else:
            print(f"Destination '{city_name}' not found.")
            return False

    def update_destination(self, city_name, new_data):
        found = False
        for dest in self.destinations:
            if dest.city.lower() == city_name.lower():
                dest.update_details(
                    new_city=new_data.get('city'),
                    new_country=new_data.get('country'),
                    new_start_date=new_data.get('start_date'),
                    new_end_date=new_data.get('end_date'),
                    new_budget=new_data.get('budget'),
                    new_activities=new_data.get('activities')
                )
                print(f"Destination '{city_name}' updated successfully.")
                found = True
                break
        if not found:
            print(f"Destination '{city_name}' not found.")
        return found

    def view_all_destinations(self):
        if not self.destinations:
            print("No destinations added yet.")
            return

        print("\n--- All Destinations ---")
        # Header for tabular format
        print(f"{'City':<15} {'Country':<15} {'Start Date':<12} {'End Date':<12} {'Budget':<10} {'Activities'}")
        print("-" * 80)
        for i, dest in enumerate(self.destinations):
            # Truncate activities if too long for display
            activities_str = ", ".join(dest.activities)
            if len(activities_str) > 30:
                activities_str = activities_str[:27] + "..."
            print(f"{dest.city:<15} {dest.country:<15} {dest.start_date:<12} {dest.end_date:<12} {dest.budget:<10.2f} {activities_str}")
        print("------------------------\n")


    def search_destination(self, keyword, search_type='city'):
        found_destinations = []
        keyword_lower = keyword.lower()
        for dest in self.destinations:
            if search_type == 'city' and dest.city.lower() == keyword_lower:
                found_destinations.append(dest)
            elif search_type == 'country' and dest.country.lower() == keyword_lower:
                found_destinations.append(dest)
            elif search_type == 'activity':
                if any(keyword_lower in activity.lower() for activity in dest.activities):
                    found_destinations.append(dest)
        return found_destinations

    def save_to_file(self):
        if not os.path.exists(os.path.dirname(self.filename)):
            os.makedirs(os.path.dirname(self.filename))
        try:
            with open(self.filename, 'w') as f:
                json.dump([d.to_dict() for d in self.destinations], f, indent=4)
            print("Itinerary saved successfully.")
            return True
        except IOError as e:
            print(f"Error saving itinerary: {e}")
            return False

    def load_from_file(self):
        if not os.path.exists(self.filename):
            print("No saved itinerary found. Starting fresh.")
            return False
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                self.destinations = [Destination.from_dict(d) for d in data]
            print("Itinerary loaded successfully.")
            return True
        except json.JSONDecodeError:
            print("Error reading itinerary file. It might be corrupted.")
            return False
        except IOError as e:
            print(f"Error loading itinerary: {e}")
            return False

    def get_destination_by_city(self, city_name):
        for dest in self.destinations:
            if dest.city.lower() == city_name.lower():
                return dest
        return None

    # Optional: Bonus feature - Sorting
    def sort_destinations(self, sort_by='start_date'):
        if sort_by == 'start_date':
            self.destinations.sort(key=lambda d: d.start_date)
        elif sort_by == 'budget':
            self.destinations.sort(key=lambda d: d.budget)
        else:
            print("Invalid sort key. Options are 'start_date' or 'budget'.")
            return
        print(f"Destinations sorted by {sort_by}.")