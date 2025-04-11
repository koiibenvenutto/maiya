"""
Webflow API client for interacting with the Webflow CMS.
"""
import os
import json
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WebflowClient:
    """
    Client for the Webflow API.
    """
    
    def __init__(self):
        """Initialize the Webflow client."""
        self.api_key = os.getenv("WEBFLOW_API_KEY")
        self.site_id = os.getenv("WEBFLOW_SITE_ID")
        
        if not self.api_key:
            raise ValueError("WEBFLOW_API_KEY environment variable not found. Please add it to your .env file.")
        
        if not self.site_id:
            raise ValueError("WEBFLOW_SITE_ID environment variable not found. Please add it to your .env file.")
        
        self.base_url = "https://api.webflow.com/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Print authentication info for debugging
        print(f"Webflow API authentication setup:")
        print(f"  Site ID: {self.site_id}")
        print(f"  API Key: {self.api_key[:5]}...{self.api_key[-5:]} (length: {len(self.api_key)})")
        print(f"  Authorization header: {self.headers['Authorization'][:12]}...{self.headers['Authorization'][-5:]}")
    
    def get_collections(self) -> List[Dict[str, Any]]:
        """
        Get all collections from the Webflow site.
        
        Returns:
            List of collection objects
        """
        url = f"{self.base_url}/sites/{self.site_id}/collections"
        print(f"  Making API request to: {url}")
        print(f"  Headers: Authorization: Bearer {self.api_key[:5]}...{self.api_key[-5:]}, accept: {self.headers['accept']}")
        
        try:
            response = requests.get(url, headers=self.headers)
            
            print(f"  Response status: {response.status_code}")
            print(f"  Response body preview: {response.text[:200]}")
            
            if not response.ok:
                print(f"  Full error response: {response.text}")
                
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  Exception: {str(e)}")
            raise
    
    def get_collection_items(self, collection_id: str) -> List[Dict[str, Any]]:
        """
        Get all items from a specific collection.
        
        Args:
            collection_id: ID of the collection
            
        Returns:
            List of collection items
        """
        url = f"{self.base_url}/collections/{collection_id}/items"
        params = {
            "offset": 0,
            "limit": 100
        }
        print(f"  Making API request to: {url}")
        print(f"  Headers: Authorization: Bearer {self.api_key[:5]}...{self.api_key[-5:]}, accept: {self.headers['accept']}")
        print(f"  Params: {params}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            print(f"  Response status: {response.status_code}")
            print(f"  Response body preview: {response.text[:200]}")
            
            if not response.ok:
                print(f"  Full error response: {response.text}")
                
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            print(f"  Exception: {str(e)}")
            raise
    
    def get_item(self, collection_id: str, item_id: str) -> Dict[str, Any]:
        """
        Get a specific item from a collection.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item
            
        Returns:
            Item object
        """
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def create_item(self, collection_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new item in a collection that will be immediately published to the live site.
        
        Args:
            collection_id: ID of the collection
            item_data: Data for the new item
            
        Returns:
            Created item object
        """
        url = f"{self.base_url}/collections/{collection_id}/items/live"
        
        # V2 API requires fieldData property instead of fields
        payload = {
            "fieldData": item_data,
            "isCmsItemInstance": True,
            "isArchived": False
        }
        
        # Log the request payload
        print(f"  Creating live item with payload: {json.dumps(payload, indent=2)[:200]}...")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload)
            
            if not response.ok:
                print(f"  Error response from Webflow: {response.status_code}")
                print(f"  Response body: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Request error: {str(e)}")
            raise
    
    def update_item(self, collection_id: str, item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing item in a collection.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item to update
            item_data: Updated data for the item
            
        Returns:
            Updated item object
        """
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}"
        
        # V2 API requires fieldData property instead of fields
        payload = {
            "fieldData": item_data,
            "isCmsItemInstance": True,
            "isArchived": False
        }
        
        # Log the request payload
        print(f"  Updating item with payload: {json.dumps(payload, indent=2)[:200]}...")
        
        try:
            response = requests.patch(url, headers=self.headers, json=payload)
            
            if not response.ok:
                print(f"  Error response from Webflow: {response.status_code}")
                print(f"  Response body: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Request error: {str(e)}")
            raise
    
    def delete_item(self, collection_id: str, item_id: str) -> Dict[str, Any]:
        """
        Delete an item from a collection.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item to delete
            
        Returns:
            Response object or empty dict if no content
        """
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}"
        print(f"  Sending DELETE request to: {url}")
        
        try:
            response = requests.delete(url, headers=self.headers)
            
            if not response.ok:
                print(f"  Error deleting item: {response.status_code}")
                print(f"  Response body: {response.text}")
                
            response.raise_for_status()
            
            # Check if the response has content before trying to parse it as JSON
            if response.text.strip():
                return response.json()
            else:
                print(f"  Delete successful (empty response)")
                return {}
        except Exception as e:
            print(f"  Delete error: {str(e)}")
            raise
    
    def find_item_by_slug(self, collection_id: str, slug: str) -> Optional[Dict[str, Any]]:
        """
        Find an item by its slug.
        
        Args:
            collection_id: ID of the collection
            slug: Slug to search for
            
        Returns:
            Item object if found, None otherwise
        """
        items = self.get_collection_items(collection_id)
        for item in items:
            if item.get("slug") == slug:
                return item
        return None
    
    def get_site_info(self) -> Dict[str, Any]:
        """
        Get information about the current site.
        
        Returns:
            Site information object
        """
        url = f"{self.base_url}/sites/{self.site_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def publish_site(self, domains: List[str] = None) -> Dict[str, Any]:
        """
        Publish the site to make all changes live.
        
        Args:
            domains: Optional list of domain IDs to publish to. If not provided, 
                    will publish to all domains associated with the site.
                    
        Returns:
            Response object with publish status
        """
        url = f"{self.base_url}/sites/{self.site_id}/publish"
        
        payload = {}
        if domains:
            payload["domains"] = domains
            
        print(f"Publishing site {self.site_id} to make all changes live...")
        response = requests.post(url, headers=self.headers, json=payload)
        
        if not response.ok:
            print(f"Error publishing site: {response.status_code}")
            print(f"Response body: {response.text}")
            
        response.raise_for_status()
        return response.json()
    
    def publish_collection_items(self, collection_id: str, item_ids: List[str] = None) -> Dict[str, Any]:
        """
        Publish multiple items in a collection at once.
        
        Args:
            collection_id: ID of the collection
            item_ids: Optional list of item IDs to publish. If not provided,
                     all items in the collection will be published.
                    
        Returns:
            Response object with publish status
        """
        url = f"{self.base_url}/collections/{collection_id}/items/live"
        
        payload = {}
        if item_ids:
            payload["itemIds"] = item_ids
            
        print(f"Publishing items in collection {collection_id}...")
        response = requests.post(url, headers=self.headers, json=payload)
        
        if not response.ok:
            print(f"Error publishing collection items: {response.status_code}")
            print(f"Response body: {response.text}")
            
        response.raise_for_status()
        return response.json()
    
    def publish_item(self, collection_id: str, item_id: str) -> Dict[str, Any]:
        """
        Publish a single item in a collection.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item to publish
                    
        Returns:
            Response object with publish status
        """
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}/live"
        
        print(f"Publishing item {item_id} in collection {collection_id}...")
        response = requests.post(url, headers=self.headers)
        
        if not response.ok:
            print(f"Error publishing item: {response.status_code}")
            print(f"Response body: {response.text}")
            
        response.raise_for_status()
        return response.json()
    
    def get_collection_fields(self, collection_id: str) -> Dict[str, Any]:
        """
        Get the fields (schema) for a specific collection.
        
        Args:
            collection_id: ID of the collection
            
        Returns:
            Collection schema with field definitions
        """
        url = f"{self.base_url}/collections/{collection_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        
        # Extract fields from the collection
        fields = data.get("fields", [])
        
        # Format fields in a more readable way
        field_info = {}
        for field in fields:
            field_info[field.get("slug")] = {
                "name": field.get("name"),
                "type": field.get("type"),
                "required": field.get("required", False)
            }
        
        return field_info

# Initialize client on module import
webflow_client = WebflowClient() 