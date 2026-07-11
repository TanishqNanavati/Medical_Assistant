import sys
from services.image_processor import image_processor

if __name__ == "__main__":
    image_path = sys.argv[1]
    print(f"Loading image from {image_path}")
    try:
        docs = image_processor.load(image_path)
        print("Successfully loaded image!")
        print("Page Content:")
        print(docs[0].page_content)
    except Exception as e:
        print("Error processing image:")
        print(e)
