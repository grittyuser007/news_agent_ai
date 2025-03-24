"""
Topic extraction module for News Analyzer
"""
import yake
import spacy
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from keybert import KeyBERT
import logging

logger = logging.getLogger(__name__)

class TopicExtractor:
    """Extract key topics and entities from text"""
    
    def __init__(self, use_spacy=True, use_keybert=True):
        """Initialize the topic extractor with selected models"""
        self.use_spacy = use_spacy
        self.use_keybert = use_keybert
        
        # Initialize models
        try:
            # YAKE for fast keyword extraction
            self.kw_extractor = yake.KeywordExtractor(
                lan="en", 
                n=2,  # ngrams
                dedupLim=0.7,  # deduplication threshold
                dedupFunc='seqm',  # deduplication function
                windowsSize=2,  # window size
                top=10  # number of keywords to extract
            )
            
            # Load models that require more resources only if specified
            if use_spacy:
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    # Download the model if not available
                    logger.info("Downloading spaCy model...")
                    spacy.cli.download("en_core_web_sm")
                    self.nlp = spacy.load("en_core_web_sm")
            
            if use_keybert:
                self.keybert_model = KeyBERT()
                
        except Exception as e:
            logger.error(f"Error initializing topic extractor: {e}")
            # Fall back to simple methods if initialization fails
            self.use_spacy = False
            self.use_keybert = False
    
    def extract_topics(self, text, num_topics=5):
        """
        Extract topics from text using multiple techniques
        Returns a dictionary with different topic extraction results
        """
        if not text or len(text) < 100:
            return {
                'keywords': [],
                'entities': [],
                'keybert': []
            }
        
        results = {}
        
        # 1. Extract keywords with YAKE
        try:
            keywords = self.kw_extractor.extract_keywords(text)
            # Sort by score (lower is better in YAKE) and get only the terms
            results['keywords'] = [kw[0] for kw in sorted(keywords, key=lambda x: x[1])[:num_topics]]
        except Exception as e:
            logger.error(f"YAKE extraction error: {e}")
            results['keywords'] = self._extract_simple_keywords(text, num_topics)
        
        # 2. Extract named entities with spaCy if available
        if self.use_spacy:
            try:
                doc = self.nlp(text[:10000])  # Limit text length for performance
                # Count entity frequencies
                entity_counts = Counter([ent.text.lower() for ent in doc.ents 
                                      if len(ent.text) > 3])
                # Get the most common entities
                results['entities'] = [item[0] for item in entity_counts.most_common(num_topics)]
            except Exception as e:
                logger.error(f"Entity extraction error: {e}")
                results['entities'] = []
        else:
            results['entities'] = []
        
        # 3. Use KeyBERT for extraction if available
        if self.use_keybert:
            try:
                keybert_keywords = self.keybert_model.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 2),
                    stop_words='english', 
                    use_maxsum=True,
                    nr_candidates=20,
                    top_n=num_topics
                )
                results['keybert'] = [kw[0] for kw in keybert_keywords]
            except Exception as e:
                logger.error(f"KeyBERT extraction error: {e}")
                results['keybert'] = []
        else:
            results['keybert'] = []
            
        return results
    
    def _extract_simple_keywords(self, text, num_topics=5):
        """Simple keyword extraction fallback using CountVectorizer"""
        try:
            # Create a list of custom stopwords
            stopwords = set(['the', 'and', 'to', 'of', 'a', 'in', 'that', 'is', 'it', 'was',
                          'for', 'on', 'with', 'as', 'at', 'by', 'this', 'be', 'are'])
            
            # Use CountVectorizer to extract n-grams
            vectorizer = CountVectorizer(
                ngram_range=(1, 2),  # use 1 and 2-grams
                stop_words=list(stopwords),
                max_features=100
            )
            
            # Fit and extract the most common n-grams
            try:
                X = vectorizer.fit_transform([text])
                words_freq = [(word, X[0, idx]) for word, idx in vectorizer.vocabulary_.items()]
                words_freq = sorted(words_freq, key=lambda x: x[1], reverse=True)
                return [word for word, freq in words_freq[:num_topics]]
            except:
                # If that fails, use a very simple word frequency approach
                words = text.lower().split()
                words = [word for word in words if word not in stopwords and len(word) > 3]
                word_freq = Counter(words)
                return [word for word, freq in word_freq.most_common(num_topics)]
        except Exception as e:
            logger.error(f"Simple keyword extraction error: {e}")
            return []
    
    def get_topic_highlights(self, text, num_topics=5):
        """
        Get a consolidated list of topics with tags identifying the method.
        Returns a list of (topic, method) tuples.
        """
        topics_dict = self.extract_topics(text, num_topics)
        
        # Combine all topics with their source
        all_topics = [
            (topic, "keyword") for topic in topics_dict['keywords']
        ] + [
            (topic, "entity") for topic in topics_dict['entities']
        ] + [
            (topic, "concept") for topic in topics_dict['keybert']
        ]
        
        # Remove duplicates (case-insensitive comparison)
        seen = set()
        unique_topics = []
        for topic, method in all_topics:
            topic_lower = topic.lower()
            if topic_lower not in seen:
                seen.add(topic_lower)
                unique_topics.append((topic, method))
        
        return unique_topics[:num_topics]