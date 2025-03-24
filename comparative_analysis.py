"""
Comparative analysis module for News Analyzer
"""

import pandas as pd
import numpy as np
from collections import Counter
import spacy
import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime

logger = logging.getLogger(__name__)

class ComparativeAnalyzer:
    """Compare multiple news articles to highlight differences and similarities"""
    
    def __init__(self, use_spacy=True):
        """Initialize the comparative analyzer with selected models"""
        self.use_spacy = use_spacy
        
        # Initialize NLP components
        try:
            if use_spacy:
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    # Download the model if not available
                    logger.info("Downloading spaCy model...")
                    import spacy.cli
                    spacy.cli.download("en_core_web_sm")
                    self.nlp = spacy.load("en_core_web_sm")
            
            # TF-IDF Vectorizer for content similarity
            self.vectorizer = TfidfVectorizer(stop_words='english', 
                                            max_features=5000,
                                            ngram_range=(1, 2))
                
        except Exception as e:
            logger.error(f"Error initializing comparative analyzer: {e}")
            self.use_spacy = False
    
    def get_entity_comparison(self, articles):
        """
        Extract and compare named entities across articles
        Returns a DataFrame with entity frequencies by article
        """
        if not articles or len(articles) < 2 or not self.use_spacy:
            return None
        
        try:
            # Extract entities from each article
            article_entities = []
            article_titles = []
            
            for article in articles:
                if not article.get('content'):
                    continue
                    
                # Limit text length for performance
                doc = self.nlp(article['content'][:10000])
                
                # Extract entities and their types
                entities = Counter()
                for ent in doc.ents:
                    # Only include longer, more significant entities
                    if len(ent.text.strip()) > 2:
                        # Use the format "text (TYPE)" for display
                        entity_key = f"{ent.text} ({ent.label_})"
                        entities[entity_key] += 1
                
                # Keep only top entities to avoid cluttering the analysis
                top_entities = dict(entities.most_common(15))
                
                article_entities.append(top_entities)
                article_titles.append(article.get('title', f"Article {len(article_titles)+1}"))
            
            # Convert to DataFrame for easier comparison
            if not article_entities:
                return None
                
            # Create DataFrame with entities as indices and article titles as columns
            df = pd.DataFrame(article_entities, index=article_titles)
            
            # Fill NaN with 0 for proper comparison
            df = df.fillna(0)
            
            # Add total count column
            df['Total Mentions'] = df.sum(axis=0)
            
            # Sort by total mentions
            df = df.sort_values('Total Mentions', axis=1, ascending=False)
            
            # Keep only entities mentioned in more than one article or mentioned multiple times
            significant_columns = [col for col in df.columns if col != 'Total Mentions' and 
                                (df[col].astype(bool).sum() > 1 or df[col].sum() > 2)]
            significant_columns.append('Total Mentions')  # Keep the total column
            
            # If we have significant columns, filter the DataFrame
            if significant_columns:
                df = df[significant_columns]
            
            return df
            
        except Exception as e:
            logger.error(f"Entity comparison failed: {e}")
            return None
    
    def get_sentiment_comparison(self, articles):
        """
        Compare sentiment across articles
        Returns a DataFrame with sentiment scores by article
        """
        if not articles or len(articles) < 2:
            return None
            
        try:
            from textblob import TextBlob
            
            article_titles = []
            sentiment_data = []
            
            for article in articles:
                if not article.get('content'):
                    continue
                    
                # Get title (truncated if needed)
                title = article.get('title', 'Untitled')
                if len(title) > 50:
                    title = title[:47] + '...'
                article_titles.append(title)
                
                # Calculate sentiment
                analysis = TextBlob(article['content'])
                sentiment_data.append({
                    'Polarity': round(analysis.sentiment.polarity, 3),
                    'Subjectivity': round(analysis.sentiment.subjectivity, 3)
                })
            
            # Create DataFrame
            df = pd.DataFrame(sentiment_data, index=article_titles)
            return df
            
        except Exception as e:
            logger.error(f"Sentiment comparison failed: {e}")
            return None
    
    def get_content_similarity_matrix(self, articles):
        """
        Calculate content similarity between articles
        Returns a similarity matrix
        """
        if not articles or len(articles) < 2:
            return None
        
        try:
            # Extract content and titles
            contents = []
            titles = []
            
            for article in articles:
                if article.get('content'):
                    contents.append(article['content'])
                    titles.append(article.get('title', 'Untitled'))
            
            if len(contents) < 2:
                return None
                
            # Calculate TF-IDF
            tfidf_matrix = self.vectorizer.fit_transform(contents)
            
            # Calculate cosine similarity
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Create DataFrame with article titles
            df = pd.DataFrame(similarity_matrix, index=titles, columns=titles)
            
            return df
            
        except Exception as e:
            logger.error(f"Content similarity calculation failed: {e}")
            return None
    
    def get_key_phrase_comparison(self, articles):
        """
        Extract and compare key phrases across articles
        Returns a DataFrame with phrase frequencies by article
        """
        if not articles or len(articles) < 2:
            return None
            
        try:
            # Use TF-IDF to extract important phrases
            article_contents = []
            article_titles = []
            
            for article in articles:
                if article.get('content'):
                    article_contents.append(article['content'])
                    article_titles.append(article.get('title', 'Untitled'))
            
            if len(article_contents) < 2:
                return None
                
            # Create TF-IDF vectorizer that keeps track of vocabulary
            phrase_vectorizer = TfidfVectorizer(
                stop_words='english',
                ngram_range=(2, 3),  # Bi-grams and tri-grams
                max_features=20  # Only keep top phrases
            )
            
            # Calculate TF-IDF
            tfidf_matrix = phrase_vectorizer.fit_transform(article_contents)
            
            # Get feature names (phrases)
            feature_names = phrase_vectorizer.get_feature_names_out()
            
            # Create a list to store phrase frequencies for each article
            phrase_data = []
            
            for i, article in enumerate(article_contents):
                # Get scores for this article
                article_scores = tfidf_matrix[i].toarray()[0]
                
                # Create dictionary of phrase -> score
                phrase_scores = {feature_names[j]: article_scores[j] 
                               for j in range(len(feature_names))
                               if article_scores[j] > 0}
                
                # Sort by score and take top phrases
                phrase_data.append(phrase_scores)
            
            # Create DataFrame
            df = pd.DataFrame(phrase_data, index=article_titles)
            
            # Fill NaN with 0
            df = df.fillna(0)
            
            # Filter to keep only phrases that appear in more than one article
            cols_to_keep = [col for col in df.columns if df[col].astype(bool).sum() > 1]
            
            if cols_to_keep:
                df = df[cols_to_keep]
                
                # Normalize scores for better comparison
                for col in df.columns:
                    if df[col].max() > 0:
                        df[col] = df[col] / df[col].max()
            
            return df
            
        except Exception as e:
            logger.error(f"Key phrase comparison failed: {e}")
            return None
    
    def generate_comparative_analysis(self, articles):
        """
        Generate a comprehensive comparative analysis of articles
        Returns a dictionary with various analysis components
        """
        if not articles or len(articles) < 2:
            return {
                "error": "Need at least 2 articles for comparison",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # Initialize results dictionary
        analysis = {
            "article_count": len(articles),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sources": [article.get('source', 'Unknown') for article in articles]
        }
        
        # Entity comparison
        entity_df = self.get_entity_comparison(articles)
        if entity_df is not None and not entity_df.empty:
            # Convert to HTML for display in Streamlit
            analysis["entity_comparison"] = entity_df.to_html(classes='table table-striped')
            
            # Generate entity heatmap
            try:
                fig, ax = plt.figure(figsize=(12, 8)), plt.gca()
                entity_df_vis = entity_df.drop(columns=['Total Mentions'])
                
                # Only show top entities if there are many
                if entity_df_vis.shape[1] > 10:
                    entity_df_vis = entity_df_vis.iloc[:, :10]
                
                im = ax.imshow(entity_df_vis.values, cmap='YlOrRd')
                
                # Set labels
                ax.set_xticks(np.arange(len(entity_df_vis.columns)))
                ax.set_yticks(np.arange(len(entity_df_vis.index)))
                
                # Label axes
                ax.set_xticklabels(entity_df_vis.columns, rotation=45, ha='right')
                ax.set_yticklabels(entity_df_vis.index)
                
                # Add colorbar
                plt.colorbar(im, ax=ax, label='Mention Count')
                
                # Add title
                plt.title('Entity Comparison Across Articles')
                plt.tight_layout()
                
                # Save figure to a bytes buffer
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                
                # Encode as base64 for HTML display
                analysis["entity_heatmap"] = base64.b64encode(buf.read()).decode()
                plt.close()
            except Exception as e:
                logger.error(f"Entity heatmap generation failed: {e}")
        
        # Sentiment comparison
        sentiment_df = self.get_sentiment_comparison(articles)
        if sentiment_df is not None and not sentiment_df.empty:
            analysis["sentiment_comparison"] = sentiment_df.to_html(classes='table table-striped')
            
            # Generate sentiment bar chart
            try:
                fig, ax = plt.figure(figsize=(10, 6)), plt.gca()
                sentiment_df.plot(kind='bar', ax=ax)
                plt.title('Sentiment Comparison')
                plt.ylabel('Score (-1 to 1)')
                plt.tight_layout()
                
                # Save figure to a bytes buffer
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                
                # Encode as base64 for HTML display
                analysis["sentiment_chart"] = base64.b64encode(buf.read()).decode()
                plt.close()
            except Exception as e:
                logger.error(f"Sentiment chart generation failed: {e}")
        
        # Content similarity
        similarity_df = self.get_content_similarity_matrix(articles)
        if similarity_df is not None and not similarity_df.empty:
            analysis["similarity_matrix"] = similarity_df.to_html(classes='table table-striped')
            
            # Generate similarity heatmap
            try:
                fig, ax = plt.figure(figsize=(10, 8)), plt.gca()
                im = ax.imshow(similarity_df.values, cmap='Blues')
                
                # Set labels
                ax.set_xticks(np.arange(len(similarity_df.columns)))
                ax.set_yticks(np.arange(len(similarity_df.index)))
                
                # Label axes
                ax.set_xticklabels(similarity_df.columns, rotation=45, ha='right')
                ax.set_yticklabels(similarity_df.index)
                
                # Add colorbar
                plt.colorbar(im, ax=ax, label='Similarity Score')
                
                # Add title
                plt.title('Content Similarity Between Articles')
                plt.tight_layout()
                
                # Loop over data dimensions and create text annotations
                for i in range(len(similarity_df.index)):
                    for j in range(len(similarity_df.columns)):
                        if i != j:  # Skip diagonal (self-similarity)
                            text = ax.text(j, i, f"{similarity_df.iloc[i, j]:.2f}",
                                        ha="center", va="center", color="black")
                
                # Save figure to a bytes buffer
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                
                # Encode as base64 for HTML display
                analysis["similarity_heatmap"] = base64.b64encode(buf.read()).decode()
                plt.close()
            except Exception as e:
                logger.error(f"Similarity heatmap generation failed: {e}")
        
        # Key phrase comparison
        phrase_df = self.get_key_phrase_comparison(articles)
        if phrase_df is not None and not phrase_df.empty:
            analysis["phrase_comparison"] = phrase_df.to_html(classes='table table-striped')
        
        return analysis