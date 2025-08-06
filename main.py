# main.py
# ...
ai_assistant = AITravelAssistant()
# ...

from itinerary_manager import ItineraryManager
from ai_assistant import AITravelAssistant
import re
import os

# --- Configuration ---
# Replace with your actual OpenAI API Key
# It's better to load this from an environment variable (e.g., using python-dotenv)
# For this project, you can put it directly here.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Create the data directory if it doesn't exist
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

itinerary_manager = ItineraryManager()
ai_assistant = AITravelAssistant(OPENAI_API_KEY)

def display_menu():
    print("\n--- AI Travel Itinerary Planner Menu ---")
    print("1. Add Destination")
    print("2. Remove Destination")
    print("3. Update Destination")
    print("4. View All Destinations")
    print("5. Search Destination")
    print("6. AI Travel Assistance")
    print("7. Save Itinerary")
    print("8. Load Itinerary")
    print("9. Exit")
    print("----------------------------------------")

def get_valid_date_input(prompt):
    while True:
        date_str = input(prompt).strip()
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str):
            return date_str
        else:
            print("Invalid date format. Please use YYYY-MM-DD.")

def get_valid_float_input(prompt):
    while True:
        try:
            value = float(input(prompt).strip())
            if value > 0:
                return value
            else:
                print("Budget must be a positive number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def get_valid_activities_input(prompt):
    while True:
        activities_str = input(prompt).strip()
        if activities_str:
            return [a.strip() for a in activities_str.split(',')]
        else:
            print("Activities cannot be empty. Please enter at least one activity, comma-separated.")

def add_destination_ui():
    print("\n--- Add New Destination ---")
    city = input("Enter city: ").strip()
    country = input("Enter country: ").strip()
    start_date = get_valid_date_input("Enter start date (YYYY-MM-DD): ")
    end_date = get_valid_date_input("Enter end date (YYYY-MM-DD): ")
    budget = get_valid_float_input("Enter budget (e.g., 1200.50): ")
    activities = get_valid_activities_input("Enter activities (comma-separated, e.g., Museum, Beach): ")

    destination_data = {
        'city': city,
        'country': country,
        'start_date': start_date,
        'end_date': end_date,
        'budget': budget,
        'activities': activities
    }
    itinerary_manager.add_destination(destination_data)

def remove_destination_ui():
    print("\n--- Remove Destination ---")
    city = input("Enter the city of the destination to remove: ").strip()
    itinerary_manager.remove_destination(city)

def update_destination_ui():
    print("\n--- Update Destination ---")
    city_to_update = input("Enter the city of the destination to update: ").strip()
    existing_dest = itinerary_manager.get_destination_by_city(city_to_update)

    if not existing_dest:
        print(f"Destination '{city_to_update}' not found.")
        return

    print(f"Current details for {existing_dest.city}:")
    print(existing_dest)

    new_data = {}
    print("Enter new values (leave blank to keep current):")
    new_city = input(f"New City (current: {existing_dest.city}): ").strip()
    if new_city: new_data['city'] = new_city

    new_country = input(f"New Country (current: {existing_dest.country}): ").strip()
    if new_country: new_data['country'] = new_country

    new_start_date = input(f"New Start Date (YYYY-MM-DD) (current: {existing_dest.start_date}): ").strip()
    if new_start_date: new_data['start_date'] = new_start_date

    new_end_date = input(f"New End Date (YYYY-MM-DD) (current: {existing_dest.end_date}): ").strip()
    if new_end_date: new_data['end_date'] = new_end_date

    new_budget_str = input(f"New Budget (e.g., 1500.00) (current: {existing_dest.budget:,.2f}): ").strip()
    if new_budget_str:
        try:
            new_data['budget'] = float(new_budget_str)
        except ValueError:
            print("Invalid budget format. Keeping original.")

    new_activities_str = input(f"New Activities (comma-separated) (current: {', '.join(existing_dest.activities)}): ").strip()
    if new_activities_str:
        new_data['activities'] = [a.strip() for a in new_activities_str.split(',')]
        if not new_data['activities']: # Ensure list is not empty after splitting
            print("Activities cannot be empty. Keeping original.")
            del new_data['activities'] # Remove invalid entry

    if new_data:
        itinerary_manager.update_destination(city_to_update, new_data)
    else:
        print("No updates provided.")


def search_destination_ui():
    print("\n--- Search Destination ---")
    search_type = input("Search by (city/country/activity): ").strip().lower()
    keyword = input(f"Enter {search_type} keyword: ").strip()

    if search_type not in ['city', 'country', 'activity']:
        print("Invalid search type. Please choose 'city', 'country', or 'activity'.")
        return

    found_destinations = itinerary_manager.search_destination(keyword, search_type)
    if found_destinations:
        print("\n--- Search Results ---")
        for dest in found_destinations:
            print(dest)
            print("-" * 20)
    else:
        print(f"No destinations found matching '{keyword}' by '{search_type}'.")

def ai_travel_assistance_ui():
    print("\n--- AI Travel Assistance ---")
    city = input("Enter the city for AI assistance: ").strip()
    destination = itinerary_manager.get_destination_by_city(city)

    if destination:
        print("\n--- AI Options ---")
        print("1. Generate Daily Itinerary")
        print("2. Generate Budget Tips")
        choice = input("Enter your choice: ").strip()

        if choice == '1':
            itinerary = ai_assistant.generate_itinerary(destination)
            print("\n--- Generated Itinerary ---")
            print(itinerary)
        elif choice == '2':
            tips = ai_assistant.generate_budget_tips(destination)
            print("\n--- Budget Tips ---")
            print(tips)
        else:
            print("Invalid AI option.")
    else:
        print(f"Destination '{city}' not found.")

def main():
    while True:
        display_menu()
        choice = input("Enter your choice (1-9): ").strip()

        if choice == '1':
            add_destination_ui()
        elif choice == '2':
            remove_destination_ui()
        elif choice == '3':
            update_destination_ui()
        elif choice == '4':
            itinerary_manager.view_all_destinations()
            # Optional: Ask user if they want to sort
            if itinerary_manager.destinations:
                sort_choice = input("Sort destinations? (y/n): ").strip().lower()
                if sort_choice == 'y':
                    sort_by = input("Sort by (start_date/budget): ").strip().lower()
                    itinerary_manager.sort_destinations(sort_by)
                    itinerary_manager.view_all_destinations() # Display again after sorting
        elif choice == '5':
            search_destination_ui()
        elif choice == '6':
            ai_travel_assistance_ui()
        elif choice == '7':
            itinerary_manager.save_to_file()
        elif choice == '8':
            itinerary_manager.load_from_file()
        elif choice == '9':
            print("Exiting and saving data...")
            itinerary_manager.save_to_file()
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please enter a number between 1 and 9.")

if __name__ == "__main__":
    main()