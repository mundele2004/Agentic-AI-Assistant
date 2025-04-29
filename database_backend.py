import sqlite3

DB_PATH = "chatbot.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    """
    Create the chat_titles table if it doesn't exist.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_titles (
            thread_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_chat_title(thread_id: str, title: str):
    """
    Save or update a chat title.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO chat_titles(thread_id, title)
        VALUES (?, ?)
        """,
        (thread_id, title),
    )

    conn.commit()
    conn.close()


def load_all_titles() -> dict[str, str]:
    """
    Returns:
        {
            thread_id: title
        }
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT thread_id, title
        FROM chat_titles
        """
    )

    rows = cursor.fetchall()

    conn.close()

    return {
        thread_id: title
        for thread_id, title in rows
    }


def load_chat_title(thread_id: str):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT title
        FROM chat_titles
        WHERE thread_id = ?
        """,
        (thread_id,),
    )

    row = cursor.fetchone()

    conn.close()

    if row:
        return row[0]

    return None

def delete_chat_title(thread_id: str):
    """
    Delete a chat title from the database.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM chat_titles
        WHERE thread_id = ?
        """,
        (thread_id,),
    )

    conn.commit()
    conn.close()