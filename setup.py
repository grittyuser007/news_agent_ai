import nltk
import os

# Download NLTK data
nltk.download('punkt')
nltk.download('stopwords')

# Create cache directory if it doesn't exist
if not os.path.exists('./content_cache'):
    os.makedirs('./content_cache')