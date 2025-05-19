#!/usr/bin/env python3

import json
import requests
import os
from jsonschema import validate, ValidationError

schema_individual = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "maintainer": {"type": "string"},
        "hostOperatingsystem": {
            "type": "array",
            "items": {"type": "string"}
        },
        "environment": {
            "type": "array",
            "items": {"type": "string"}
        },
        "hardware": {
            "type": "object",
            "properties": {
                "chipVendor": {"type": "string"},
                "manufacturer": {"type": "string"},
                "specs": {
                    "type": "object",
                    "properties": {
                        "MCU": {"type": "string"},
                        "RAM": {"type": "string"},
                        "Flash": {"type": "string"},
                        "GPU": {"type": ["string", "null"]},
                        "Resolution": {"type": "string"},
                        "Display Size": {"type": "string"},
                        "Interface": {"type": "string"},
                        "Color Depth": {"type": "string"},
                        "Technology": {"type": "string"},
                        "DPI": {"type": "string"},
                        "Touch Pad": {"type": "string"}
                    },
                    "required": ["RAM", "Flash"]
                }
            },
            "required": ["chipVendor", "manufacturer", "specs"]
        },
        "description": {"type": "string"},
        "shortDescription": {"type": "string"},
        "urlToClone": {"type": "string"},
        "logos": {
            "type": "array",
            "items": {"type": "string"}
        },
        "image": {"type": "string"},
        "buy_now_links": {
            "type": "array",
            "items": {"type": "string"}
        },
        "branches": {
            "type": "array",
            "items": {"type": "string"}
        },
        "settings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "label": {"type": "string"},
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"},
                                "default": {"type": "string", "enum": ["true", "false"], "default": "false"}
                            },
                            "required": ["name", "value"]
                        }
                    },
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ifValue": {"type": "string"},
                                "toAppend": {"type": "string"},
                                "toReplace": {"type": "string"},
                                "newContent": {"type": "string"},
                                "filePath": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["type"]
            }
        }
    },
    "required": ["name", "maintainer", "hostOperatingsystem", "environment", "description", "shortDescription", "urlToClone", "logos", "image", "branches", "settings"]
}

schema_whole = {
   "type": "array",
    "items": schema_individual
}

headers = {} # Never print the headers as it contains a token which must not be displayed in CI logs.
bearer_token = os.environ.get("GITHUB_TOKEN")
if bearer_token is not None:
    headers["Authorization"] = f"Bearer {bearer_token}"
else:
    print("warning: no GITHUB_TOKEN in env. request limit may be exceeded")

valid_links = set()

def ensure_link_valid(link):
    if link in valid_links:
        return
    response = requests.head(link, headers=headers) # Use the HEAD method to test for existence
    response.raise_for_status() # Raise an exception for HTTP errors
    valid_links.add(link) # cache status for duplicates

# Function to validate JSON against the schema
def validate_json(json_data, schema):
    try:
        validate(instance=json_data, schema=schema)
        print("JSON is valid")
    except ValidationError as e:
        print(f"JSON validation error: {e.message}")
        if e.path:
            print(f"Error location: {' -> '.join(map(str, e.path))}")
        else:
            print("Error location: Root of the document")
        return False
    if schema is schema_individual:
        try:
            ensure_link_valid(json_data["urlToClone"])
            for logo_link in json_data["logos"]:
                ensure_link_valid(logo_link)
            ensure_link_valid(json_data["image"])
            buy_now_link = json_data.get("buy_now_link")
            if buy_now_link is not None:
                ensure_link_valid(buy_now_link)
        except requests.exceptions.RequestException as e:
            print(f"Error checking manifest link {e.request.url}: {e}")
            return False
    return True

# Function to fetch JSON content from a URL
def fetch_json(url):
    if url.startswith("file://"):
        # for local testing
        with open(url[len("file://"):]) as f:
            return json.load(f)
    response = requests.get(url, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()

# List to hold all the JSON content
all_json_data = []

# Read the file containing URLs to JSON files
with open('manifests', 'r') as file:
    urls = file.readlines()

valid = True

# Fetch and concatenate JSON data from each URL
for url in urls:
    url = url.strip()  # Remove any extra whitespace or newlines
    if url:  # Ensure the URL is not empty
        print(f"Fetching {url}")
        try:
            json_data = fetch_json(url)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching {url}: {e}")
            valid = False
            continue
        this_json_valid = validate_json(json_data, schema_individual)  # Validate each JSON fetched
        if not this_json_valid:
            print(f"Validation failed for {url}")
            valid = False
            continue
        all_json_data.append(json_data)  # Append if valid


print("Validating the concatenated JSON")
concat_valid = validate_json(all_json_data, schema_whole)
filename = "manifest_all_v1.1.0.json"
if concat_valid:
    # Save the concatenated JSON data to a new file
    with open(filename, 'w') as outfile:
        json.dump(all_json_data, outfile, indent=4)

    print(f"All JSON data has been concatenated and saved to {filename}.")
else:
    print("Error: the concatenated JSON is invalid") 
    valid = False

if not valid:
    exit(1)
