import numpy as np
import networkx as nx
import re
from collections import Counter
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download required NLTK resources silently
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.error(f"Failed to download NLTK resources: {e}")

class SummaryGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Try to load stopwords, with fallback
        try:
            self.stop_words = set(stopwords.words('english'))
        except LookupError:
            self.logger.warning("Could not load stopwords, using empty set")
            self.stop_words = set(['the', 'and', 'a', 'to', 'of', 'in', 'is', 'it', 'that'])
            
        self.cache = {}
        
    def _preprocess_text(self, text):
        """Clean and normalize text"""
        # Basic cleanup only - faster processing
        text = re.sub(r'[^\w\s\.]', '', text)
        return text.lower()
        
    def _tokenize_sentences(self, text):
        """Split text into sentences with error handling"""
        try:
            return sent_tokenize(text)
        except LookupError:
            # Fallback to simple sentence splitting if NLTK fails
            return re.split(r'(?<=[.!?])\s+', text)
        
    def _create_similarity_matrix(self, sentences):
        """Create a similarity matrix between sentences with optimizations"""
        # For shorter texts, use full matrix computation
        if len(sentences) <= 100:
            similarity_matrix = np.zeros((len(sentences), len(sentences)))
            
            # Calculate similarity for each sentence pair
            for i in range(len(sentences)):
                for j in range(i+1, len(sentences)):  # Only compute upper triangle
                    similarity = self._sentence_similarity(sentences[i], sentences[j])
                    similarity_matrix[i][j] = similarity
                    similarity_matrix[j][i] = similarity  # Mirror value
                    
            return similarity_matrix
        
        # For longer texts, use sparse approach - only compute for nearby sentences
        # This significantly reduces computation time
        else:
            similarity_matrix = np.zeros((len(sentences), len(sentences)))
            window_size = 50  # Only compare sentences within this window
            
            for i in range(len(sentences)):
                # Only compute for sentences within window
                start = max(0, i-window_size)
                end = min(len(sentences), i+window_size+1)
                
                for j in range(start, end):
                    if i != j:
                        similarity = self._sentence_similarity(sentences[i], sentences[j])
                        similarity_matrix[i][j] = similarity
                        
            return similarity_matrix
        
    def _sentence_similarity(self, sent1, sent2):
        """Calculate similarity between two sentences with optimizations"""
        # Use set operations for faster processing
        words1 = set(word.lower() for word in re.findall(r'\w+', sent1) 
                   if word.lower() not in self.stop_words and len(word) > 1)
        words2 = set(word.lower() for word in re.findall(r'\w+', sent2) 
                   if word.lower() not in self.stop_words and len(word) > 1)
        
        # If either set is empty, return 0
        if not words1 or not words2:
            return 0
        
        # Use Jaccard similarity - faster than full vector similarity
        # Jaccard = intersection / union
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0
            
        return len(intersection) / len(union)
        
    def generate_summary(self, text, ratio=0.3, min_sentences=3, max_sentences=7):
        """Generate a summary using TextRank algorithm with optimizations"""
        # Check cache first using a hash
        text_hash = hash(text[:1000])  # Use first 1000 chars for faster hashing
        if text_hash in self.cache:
            return self.cache[text_hash]
            
        # Handle edge cases
        if not text or len(text) < 100:
            return text
            
        try:
            # Skip preprocessing for longer texts
            if len(text) > 10000:
                processed_text = text
            else:
                processed_text = self._preprocess_text(text)
            
            # Split into sentences
            sentences = self._tokenize_sentences(processed_text if len(text) > 10000 else text)
            
            # Handle very short texts (fewer than 4 sentences)
            if len(sentences) <= 3:
                return text
                
            # For very long texts, sample sentences to speed up processing
            if len(sentences) > 200:
                # Take every other sentence for texts between 200-500 sentences
                if len(sentences) <= 500:
                    sentences = sentences[::2]
                # For even longer texts, take sparse samples
                else:
                    sentences = sentences[::5]
            
            # Create similarity matrix for TextRank
            similarity_matrix = self._create_similarity_matrix(sentences)
            
            # Create graph and apply PageRank with reduced iterations
            nx_graph = nx.from_numpy_array(similarity_matrix)
            scores = nx.pagerank(nx_graph, max_iter=50, tol=1e-4)
            
            # Get top sentences based on ratio or limits
            num_sentences = min(max(min_sentences, int(len(sentences) * ratio)), max_sentences)
            ranked_sentences = sorted(((scores[i], i, s) for i, s in enumerate(sentences)), reverse=True)
            
            # Sort by original position to maintain flow
            summary_sentences = sorted([item for item in ranked_sentences[:num_sentences]], key=lambda x: x[1])
            
            # Join the top sentences
            summary = ' '.join([item[2] for item in summary_sentences])
            
            # Cache the result
            self.cache[text_hash] = summary
            return summary
            
        except Exception as e:
            self.logger.error(f"Summary generation failed: {e}")
            # Simple fallback
            simple_sentences = re.split(r'(?<=[.!?])\s+', text)
            return ' '.join(simple_sentences[:min(3, len(simple_sentences))])
    
    def fast_summarize(self, text, num_sentences=3):
        """Provides a faster summary for shorter texts"""
        if not text or len(text) < 100:
            return text
        
        try:
            # Simple sentence extraction
            sentences = self._tokenize_sentences(text)
            
            if len(sentences) <= num_sentences:
                return text
            
            # Just take first sentence and a couple from the middle/end
            if len(sentences) <= 5:
                return ' '.join(sentences[:num_sentences])
            
            # For longer texts, take strategically positioned sentences
            result = [sentences[0]]  # First sentence usually has good context
            
            # Take one from middle
            middle_idx = len(sentences) // 2
            result.append(sentences[middle_idx])
            
            # Take one near end but not the last (often references, etc.)
            end_idx = min(len(sentences) - 2, len(sentences) * 3 // 4)
            result.append(sentences[end_idx])
            
            return ' '.join(result)
        except:
            # Ultra-simple fallback
            text = text.replace('\n', ' ')
            return text[:500] + "..."
            
    def batch_summarize(self, texts, ratio=0.3):
        """Process multiple texts with optimizations"""
        results = []
        for text in texts:
            results.append(self.generate_summary(text, ratio))
        return results