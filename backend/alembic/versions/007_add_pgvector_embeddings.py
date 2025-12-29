"""Add pgvector embeddings to events table

Revision ID: 007_add_pgvector_embeddings
Revises: 006_add_user_permissions
Create Date: 2025-12-29 12:00:00

This migration adds vector columns to the events table for storing
text and image embeddings, enabling semantic search via pgvector.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007_add_pgvector_embeddings'
down_revision = '006_add_user_permissions'
branch_labels = None
depends_on = None


def upgrade():
    """Add vector columns for embeddings."""
    
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Add text embedding column (384 dims - all-MiniLM-L6-v2)
    # Using raw SQL because SQLAlchemy may not have pgvector type
    op.execute("""
        ALTER TABLE events 
        ADD COLUMN IF NOT EXISTS text_embedding vector(384)
    """)
    
    # Add image embedding column (512 dims - CLIP ViT-B/32)
    op.execute("""
        ALTER TABLE events 
        ADD COLUMN IF NOT EXISTS image_embedding vector(512)
    """)
    
    # Create HNSW indexes for fast similarity search
    # HNSW is the recommended index type for pgvector
    # m = 16, ef_construction = 64 are good defaults
    
    # Index for text embeddings (cosine similarity)
    op.execute("""
        CREATE INDEX IF NOT EXISTS events_text_embedding_idx 
        ON events USING hnsw (text_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    # Index for image embeddings (cosine similarity)
    op.execute("""
        CREATE INDEX IF NOT EXISTS events_image_embedding_idx 
        ON events USING hnsw (image_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    
    # Add index on timestamp for time-range queries (if not exists)
    op.execute("""
        CREATE INDEX IF NOT EXISTS events_timestamp_idx 
        ON events (timestamp DESC)
    """)
    

def downgrade():
    """Remove vector columns and indexes."""
    
    # Drop indexes first
    op.execute("DROP INDEX IF EXISTS events_text_embedding_idx")
    op.execute("DROP INDEX IF EXISTS events_image_embedding_idx")
    
    # Drop columns
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS text_embedding")
    op.execute("ALTER TABLE events DROP COLUMN IF EXISTS image_embedding")
    
    # Note: We don't drop the pgvector extension as other tables might use it
