"""
Webflow API client for interacting with the Webflow CMS.
"""
import os
import json
import requests
import mimetypes
import random
import string
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def truncate_url(url: str, max_length: int = 60) -> str:
    """Truncate a URL for display in logs."""
    if not url or len(url) <= max_length:
        return url
    
    # Split into parts
    parts = url.split('://')
    if len(parts) < 2:
        return url[:max_length-3] + '...'
    
    protocol = parts[0]
    rest = parts[1]
    
    # Calculate how much space we have left
    remaining = max_length - len(protocol) - 6  # 6 = len('://...') + len('...')
    
    # If not enough space, just do basic truncation
    if remaining < 10:
        return url[:max_length-3] + '...'
    
    # Divide remaining space between start and end of the URL
    start_length = remaining // 2
    end_length = remaining - start_length
    
    return f"{protocol}://{rest[:start_length]}...{rest[-end_length:]}"

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
        print(f"  Making API request to: {truncate_url(url)}")
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
        print(f"  Making API request to: {truncate_url(url)}")
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
        
        # V2 API requires fieldData property in the correct format
        payload = {
            "isArchived": False,
            "isDraft": False,
            "fieldData": item_data
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
        Update an existing item in a collection and publish it live immediately.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item to update
            item_data: Updated data for the item
            
        Returns:
            Updated item object
        """
        # Use the single item live endpoint for V2 API
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}/live"
        
        # V2 API for single item update requires fieldData without an items array
        payload = {
            "isArchived": False,
            "isDraft": False,
            "fieldData": item_data
        }
        
        # Log the request payload
        print(f"  Updating item with payload: {json.dumps(payload, indent=2)[:200]}...")
        
        try:
            # Use PATCH method for updating a single item in V2 API
            response = requests.patch(url, headers=self.headers, json=payload)
            
            if not response.ok:
                print(f"  Error response from Webflow: {response.status_code}")
                print(f"  Response body: {response.text}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Request error: {str(e)}")
            raise
    
    def delete_item(self, collection_id: str, item_id: str) -> bool:
        """
        Delete an item from a collection.
        
        Args:
            collection_id: ID of the collection
            item_id: ID of the item to delete
            
        Returns:
            Boolean indicating success (True) or failure (False)
        """
        # Use the single item endpoint for V2 API
        url = f"{self.base_url}/collections/{collection_id}/items/{item_id}"
        
        print(f"  Sending DELETE request to: {truncate_url(url)}")
        
        try:
            # Use DELETE method for V2 API
            response = requests.delete(url, headers=self.headers)
            
            if not response.ok:
                print(f"  Error deleting item: {response.status_code}")
                print(f"  Response body: {response.text}")
                return False
            
            # For successful deletion (204 No Content is common)
            if response.status_code == 204 or not response.text.strip():
                print(f"  Delete successful (empty response or 204 No Content)")
                return True
                
            # If we got here, it's a success response with some content
            print(f"  Delete successful with response: {response.text[:100]}")
            return True
            
        except Exception as e:
            print(f"  Delete error: {str(e)}")
            return False
    
    def find_item_by_slug(self, collection_id: str, slug: str) -> Optional[Dict[str, Any]]:
        """
        Find an item by its slug.
        
        Args:
            collection_id: ID of the collection
            slug: Slug to search for
            
        Returns:
            Item object if found, None otherwise
        """
        # Try first with a filter query approach
        url = f"{self.base_url}/collections/{collection_id}/items"
        params = {
            "offset": 0,
            "limit": 100
        }
        
        print(f"  Searching for item with slug '{slug}' in collection {collection_id}")
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            
            if not response.ok:
                print(f"  Error fetching items: {response.status_code}")
                return None
            
            items = response.json().get("items", [])
            
            # More efficient search through items
            for item in items:
                item_slug = item.get("slug", "")
                if item_slug == slug:
                    print(f"  Found item with matching slug: {item.get('id')}")
                    return item
            
            print(f"  No item found with slug '{slug}'")
            return None
        except Exception as e:
            print(f"  Error finding item by slug: {str(e)}")
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
        
        # In Webflow, 'name' and 'slug' are typically required
        # If they're not marked as required in the schema, mark them here
        if "name" in field_info and not field_info["name"]["required"]:
            field_info["name"]["required"] = True
        
        if "slug" in field_info and not field_info["slug"]["required"]:
            field_info["slug"]["required"] = True
        
        return field_info
    
    def upload_asset(self, file_path: str, file_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Upload an asset (image, file, etc.) to the Webflow asset library using the two-step process:
        1. Get upload URL from Webflow
        2. Upload file to Amazon S3
        
        Args:
            file_path: Path to the file to upload
            file_name: Optional name for the uploaded file
            
        Returns:
            Asset object if successful, None otherwise
        """
        # Use specified name or extract from path
        if not file_name:
            file_name = os.path.basename(file_path)
        
        try:
            import hashlib
            
            # Calculate MD5 hash of the file
            with open(file_path, 'rb') as f:
                file_data = f.read()
                file_hash = hashlib.md5(file_data).hexdigest()
            
            # Step 1: Get upload URL from Webflow
            url = f"{self.base_url}/sites/{self.site_id}/assets"
            
            # Create request payload
            payload = {
                "fileName": file_name,
                "fileHash": file_hash
            }
            
            # Make the request to get upload URL
            print(f"Getting upload URL for {file_name}...")
            response = requests.post(url, headers=self.headers, json=payload)
            
            if not response.ok:
                print(f"Error getting upload URL: {response.status_code}")
                print(f"Response body: {response.text}")
                return None
            
            # Parse response to get upload details
            upload_data = response.json()
            upload_url = upload_data.get('uploadUrl')
            upload_details = upload_data.get('uploadDetails', {})
            
            if not upload_url or not upload_details:
                print(f"Invalid response from Webflow API, missing upload URL or details")
                return None
            
            print(f"Got upload URL: {truncate_url(upload_url)}")
            
            # Step 2: Upload to S3
            # Prepare the form data for S3 upload
            form_data = {}
            
            # Add all the upload details as form fields
            for key, value in upload_details.items():
                form_data[key] = value
            
            # Add the file
            file_content_type = upload_details.get('content-type') or 'application/octet-stream'
            files = {
                'file': (file_name, open(file_path, 'rb'), file_content_type)
            }
            
            # Make the S3 upload request
            print(f"Uploading file to S3...")
            s3_response = requests.post(upload_url, data=form_data, files=files)
            
            if not s3_response.ok:
                print(f"Error uploading to S3: {s3_response.status_code}")
                print(f"Response body: {s3_response.text}")
                return None
            
            print(f"File uploaded successfully")
            
            # Return the original response from Webflow which contains URLs
            asset_url = upload_data.get('assetUrl') or upload_data.get('hostedUrl')
            print(f"Asset uploaded successfully: {truncate_url(asset_url)}")
            
            # Update the response with the URL field for compatibility
            upload_data['url'] = asset_url
            
            return upload_data
        except Exception as e:
            print(f"Exception uploading asset: {str(e)}")
            return None
    
    def upload_asset_from_url(self, image_url: str, file_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Upload an asset from a URL to Webflow.
        
        Args:
            image_url: URL of the image to upload
            file_name: Optional filename to use for the uploaded asset
            
        Returns:
            Asset data including the new URL
        """
        try:
            # Generate a unique filename if none provided
            if not file_name:
                # Extract extension from URL or content type
                try:
                    ext = os.path.splitext(image_url.split('?')[0])[1]
                    if not ext:
                        ext = '.jpg'  # Default to jpg if no extension
                except:
                    ext = '.jpg'
                
                # Generate random filename with the extracted extension
                random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
                file_name = f"image_{random_str}{ext}"
            
            print(f"Uploading image from URL: {truncate_url(image_url)} as {file_name}")
            
            # Download the image
            print(f"Downloading image from {truncate_url(image_url)}")
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            # Determine content type from response or filename
            content_type = response.headers.get('Content-Type')
            if not content_type or 'text/html' in content_type:
                # Try to determine the content type from the filename
                content_type, _ = mimetypes.guess_type(file_name)
                if not content_type:
                    content_type = 'image/jpeg'  # Default to JPEG
            
            # Get file size
            file_size = len(response.content)
            print(f"Image downloaded: {file_size} bytes, type: {content_type}")
            
            # Get the upload URL from Webflow
            print(f"Getting upload URL from Webflow for {file_name}")
            upload_data = self._get_upload_url(file_name, content_type, file_size)
            
            if not upload_data or 'uploadUrl' not in upload_data:
                print(f"Failed to get upload URL from Webflow")
                return None
            
            upload_url = upload_data.get('uploadUrl')
            print(f"Got upload URL: {truncate_url(upload_url)}")
            
            # Step 2: Upload to S3
            print(f"Uploading to S3...")
            s3_upload_response = requests.put(
                upload_url,
                data=response.content,
                headers={
                    'Content-Type': content_type,
                }
            )
            
            if not s3_upload_response.ok:
                print(f"S3 upload failed: {s3_upload_response.status_code}")
                print(f"Response: {s3_upload_response.text[:500]}")
                return None
            
            print(f"S3 upload successful")
            
            # Return the original response from Webflow which contains URLs
            asset_url = upload_data.get('assetUrl') or upload_data.get('hostedUrl')
            print(f"Asset uploaded successfully: {truncate_url(asset_url)}")
            
            # Update the response with the URL field for compatibility
            upload_data['url'] = asset_url
            return upload_data
            
        except Exception as e:
            print(f"Error uploading asset from URL: {str(e)}")
            return None

# Initialize client on module import
webflow_client = WebflowClient() 