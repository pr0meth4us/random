import io
from google.cloud import vision
from google.oauth2 import service_account

def extract_text(image_path: str, credentials_path: str = None) -> str:
    """
    Extracts text from an image using Google Cloud Vision API.
    
    Args:
        image_path (str): The path to the image file.
        credentials_path (str): The path to the Google Cloud service account JSON credentials.
            If None, defaults to the GOOGLE_APPLICATION_CREDENTIALS environment variable.
            
    Returns:
        str: The raw extracted text from the image.
    """
    # Initialize the client with specific credentials if provided
    if credentials_path:
        credentials = service_account.Credentials.from_service_account_file(credentials_path)
        client = vision.ImageAnnotatorClient(credentials=credentials)
    else:
        client = vision.ImageAnnotatorClient()

    # Load the image into memory
    with io.open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)

    # Use Document Text Detection for dense/handwritten documents
    response = client.document_text_detection(image=image)
    
    if response.error.message:
        raise Exception(f"{response.error.message}\nFor more info on error messages, check: "
                        f"https://cloud.google.com/apis/design/errors")
        
    return response.full_text_annotation.text
