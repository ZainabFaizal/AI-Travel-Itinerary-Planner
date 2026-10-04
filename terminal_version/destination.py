# destination.py

import re

class Destination:
    def __init__(self, city, country, start_date, end_date, budget, activities):
        self.city = city
        self.country = country
        self.start_date = start_date
        self.end_date = end_date
        self.budget = budget
        self.activities = activities

    def update_details(self, new_city=None, new_country=None, new_start_date=None, new_end_date=None, new_budget=None, new_activities=None):
        if new_city:
            self.city = new_city
        if new_country:
            self.country = new_country
        if new_start_date and self._validate_date(new_start_date):
            self.start_date = new_start_date
        elif new_start_date:
            print("Invalid start date format. Keeping original.")
        if new_end_date and self._validate_date(new_end_date):
            self.end_date = new_end_date
        elif new_end_date:
            print("Invalid end date format. Keeping original.")
        if new_budget is not None and self._validate_budget(new_budget):
            self.budget = new_budget
        elif new_budget is not None:
            print("Invalid budget. Keeping original.")
        if new_activities is not None and self._validate_activities(new_activities):
            self.activities = new_activities
        elif new_activities is not None:
            print("Activities list cannot be empty. Keeping original.")

    def _validate_date(self, date_str):
        return bool(re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_str))

    def _validate_budget(self, budget_val):
        return isinstance(budget_val, (int, float)) and budget_val > 0

    def _validate_activities(self, activities_list):
        return isinstance(activities_list, list) and len(activities_list) > 0

    def __str__(self):
        return (f"City: {self.city}, Country: {self.country}\n"
                f"Dates: {self.start_date} to {self.end_date}\n"
                f"Budget: ${self.budget:,.2f}\n"
                f"Activities: {', '.join(self.activities)}\n")

    def to_dict(self):
        # Helper method for saving to JSON
        return {
            "city": self.city,
            "country": self.country,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "budget": self.budget,
            "activities": self.activities
        }

    @staticmethod
    def from_dict(data):
        # Helper method for loading from JSON
        return Destination(
            data['city'],
            data['country'],
            data['start_date'],
            data['end_date'],
            data['budget'],
            data['activities']
        )