"""
Utility functions for handling file uploads in the supervisor system.
Centralizes file upload parsing and validation logic.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

# Constants
FILE_UPLOAD_MARKER_PATTERN = r'\[FILE_UPLOAD:(.+):([^:]+):([^\]]+)\]'
MAX_FILE_SIZE_BASE64 = 25 * 1024 * 1024  # 25MB in base64 (roughly 18.75MB binary)
SUPPORTED_MIME_TYPES = {
    'text/plain',
    'text/markdown',
    'text/x-markdown',
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def extract_base64_from_data_url(data_url: str) -> str:
    """
    Extract base64 data from a data URL string.
    
    Args:
        data_url: Data URL in format 'data:mime/type;base64,<base64data>' or just base64 string
        
    Returns:
        Extracted base64 data string
        
    Raises:
        ValueError: If data URL format is invalid
    """
    if not data_url:
        raise ValueError("Data URL cannot be empty")
    
    # Handle data URL format: data:mime/type;base64,<base64data>
    if 'base64,' in data_url:
        return data_url.split('base64,')[1]
    elif ',' in data_url:
        # Fallback: split by comma and take last part
        return data_url.split(',')[-1]
    else:
        # Assume it's already just base64 data
        return data_url


def parse_file_upload_markers(query_text: str) -> tuple[str, List[Dict[str, str]]]:
    """
    Parse file upload markers from query text and extract file data.
    
    Args:
        query_text: Query text that may contain [FILE_UPLOAD:...] markers
        
    Returns:
        Tuple of (cleaned_query_text, list_of_file_uploads)
        Each file upload dict contains: base64_data, filename, mime_type
    """
    file_uploads: List[Dict[str, str]] = []
    clean_query = query_text
    matches = re.findall(FILE_UPLOAD_MARKER_PATTERN, query_text)
    
    for match in matches:
        data_url_part = match[0]
        filename = match[1]
        mime_type = match[2]
        
        try:
            base64_data = extract_base64_from_data_url(data_url_part)
            
            # Validate file upload
            if not base64_data:
                continue  # Skip empty files
                
            if len(base64_data) > MAX_FILE_SIZE_BASE64:
                continue  # Skip files that are too large
                
            file_uploads.append({
                'base64_data': base64_data,
                'filename': filename,
                'mime_type': mime_type
            })
            
            # Remove marker from query text
            escaped_pattern = (
                r'\[FILE_UPLOAD:' + 
                re.escape(data_url_part) + 
                r':' + 
                re.escape(filename) + 
                r':' + 
                re.escape(mime_type) + 
                r'\]'
            )
            clean_query = re.sub(escaped_pattern, f'[Uploaded file: {filename}]', clean_query)
        except (ValueError, IndexError) as e:
            # Log error but continue processing
            continue
    
    return clean_query, file_uploads


def validate_file_upload(file_upload: Dict[str, str]) -> bool:
    """
    Validate a file upload dictionary.
    
    Args:
        file_upload: Dictionary with base64_data, filename, mime_type
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(file_upload, dict):
        return False
    
    required_fields = ['base64_data', 'filename', 'mime_type']
    if not all(field in file_upload for field in required_fields):
        return False
    
    base64_data = file_upload.get('base64_data', '')
    if not base64_data or len(base64_data) == 0:
        return False
    
    if len(base64_data) > MAX_FILE_SIZE_BASE64:
        return False
    
    mime_type = file_upload.get('mime_type', '')
    if mime_type and mime_type not in SUPPORTED_MIME_TYPES:
        # Allow unsupported types but log warning
        pass
    
    return True


def normalize_file_uploads(
    structured_uploads: Optional[List[Dict[str, str]]],
    query_text: str
) -> tuple[str, List[Dict[str, str]]]:
    """
    Normalize file uploads from either structured field or query text markers.
    
    Args:
        structured_uploads: List of file upload dicts from request body (preferred)
        query_text: Query text that may contain file upload markers (fallback)
        
    Returns:
        Tuple of (cleaned_query_text, validated_file_uploads)
    """
    file_uploads: List[Dict[str, str]] = []
    
    # Prefer structured uploads if available
    if structured_uploads:
        for upload in structured_uploads:
            if validate_file_upload(upload):
                file_uploads.append(upload)
    else:
        # Fallback: parse from query text
        clean_query, parsed_uploads = parse_file_upload_markers(query_text)
        query_text = clean_query
        file_uploads.extend(parsed_uploads)
    
    return query_text, file_uploads

