import streamlit as st
from sqlalchemy import create_engine, Column, String, Integer, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from passlib.hash import bcrypt
import pandas as pd
from datetime import datetime, timedelta
import utilities as ut
import model_work as mt
import os
import io
import shutil

# -----------------------------
# Database setup
# -----------------------------
DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class User(Base):
    """
    User table with status and payment info

    Fields:
      - status: 'pending' (awaiting admin), 'active', 'paused'
      - payment_active: 0/1 flag toggled by admin when a tier is set active
      - payment_start: datetime when a tier was activated (used with 30-day window)
      - payment_tier: 0 (none), 1 (Tier 1), 2 (Tier 2), 3 (Tier 3)
        Tier semantics:
          * 1: Views Predictor only
          * 2: Similar Movies only
          * 3: Both features
    """
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    status = Column(String, default='pending')  # pending, active, paused
    payment_active = Column(Integer, default=0)  # 0 = not paid, 1 = paid
    payment_start = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # New column for tiered access:
    # Will be added to the DB at runtime if missing (see ensure_schema)
    payment_tier = Column(Integer, default=0)  # 0=none, 1,2,3

Base.metadata.create_all(engine)

def ensure_schema():
    """Ensure newly added columns exist in SQLite (idempotent)."""
    with engine.connect() as conn:
        # Check existing columns
        cols = conn.execute(text("PRAGMA table_info(users)")).fetchall()
        col_names = {c[1] for c in cols}
        # Add payment_tier if missing
        if "payment_tier" not in col_names:
            conn.execute(text("ALTER TABLE users ADD COLUMN payment_tier INTEGER DEFAULT 0"))
        conn.commit()

ensure_schema()

# -----------------------------
# Helper functions
# -----------------------------
def add_user(username, password):
    Session = sessionmaker(bind=engine)
    with Session() as session:
        hashed_password = bcrypt.hash(password)
        new_user = User(username=username.lower(), password=hashed_password)
        session.add(new_user)
        session.commit()

def get_user(username):
    Session = sessionmaker(bind=engine)
    with Session() as session:
        return session.query(User).filter_by(username=username.lower()).first()

def get_all_users():
    Session = sessionmaker(bind=engine)
    with Session() as session:
        return session.query(User).all()

def update_user_status(user_id, status):
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.status = status
            session.commit()

def set_tier_and_activate(user_id, tier: int):
    """
    Set user's payment tier and activate payment window.
    Also flips status to 'active' (if not paused) so user can log in immediately.
    """
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.payment_tier = tier
            user.payment_active = 1 if tier in (1, 2, 3) else 0
            user.payment_start = datetime.utcnow() if user.payment_active == 1 else None
            if user.status != "paused":
                user.status = "active"
            session.commit()

def update_payment(user_id, active=1):
    """Legacy toggle for payment_active; keeps payment_start in sync."""
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.payment_active = active
            user.payment_start = datetime.utcnow() if active else None
            session.commit()

def reset_password(user_id, new_password):
    Session = sessionmaker(bind=engine)
    with Session() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.password = bcrypt.hash(new_password)
            session.commit()

def zip_user_folder(username: str) -> bytes:
    """
    Create a zip of User/<username> folder and return raw bytes (for download).
    If folder doesn't exist, returns empty bytes.
    """
    folder_path = os.path.join("User", username.lower())
    if not os.path.isdir(folder_path):
        return b""
    # Make an in-memory zip
    buf = io.BytesIO()
    # Create temp archive on disk then stream into memory (shutil.make_archive requires a filename)
    tmp_base = f"{username.lower()}_bundle"
    tmp_zip_path = shutil.make_archive(tmp_base, 'zip', root_dir=folder_path)
    with open(tmp_zip_path, "rb") as f:
        buf.write(f.read())
    # Clean temp file
    os.remove(tmp_zip_path)
    buf.seek(0)
    return buf.read()

def admin_replace_dataset(username: str, df: pd.DataFrame):
    """
    Replace/initialize user's dataset.
    Uses your existing utility to lay out the user folder properly.
    """
    # Rebuild user folder structure according to your pipeline
    ut.Create_User(username.lower(), df)

# -----------------------------
# Login Page
# -----------------------------
def login_page():
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        # --- Admin login check ---
        if username == "admin" and password == "admin123":
            st.session_state.logged_in = True
            st.session_state.username = "admin"
            st.session_state.is_admin = True
            st.success("Logged in as Admin")
            st.rerun()

        # --- Normal user login check ---
        else:
            user = get_user(username)
            if user and bcrypt.verify(password, user.password):
                if user.status == "pending":
                    st.warning("Account pending admin approval.")
                elif user.status == "paused":
                    st.error("Your account has been paused by the admin.")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = user.username
                    st.session_state.is_admin = False
                    st.success(f"Welcome {username}!")
                    st.rerun()
            else:
                st.error("Invalid username or password")

# -----------------------------
# Signup Page
# -----------------------------
def signup_page():
    st.title("Signup Page")
    username = st.text_input("Choose a username")
    password = st.text_input("Choose a password", type="password")
    uploaded_file = st.file_uploader("Upload your dataset", type="csv")
    if st.button("Sign Up"):
        if username.lower() == "admin":
            st.error("Cannot sign up as admin!")
            return
        if username and password:
            if get_user(username):
                st.error("Username already exists")
            else:
                add_user(username, password)
                st.success("Account created. Waiting for admin approval.")
                if uploaded_file is not None:
                    data_for_user = pd.read_csv(uploaded_file)
                    admin_replace_dataset(username, data_for_user)
        else:
            st.error("Fill all fields")

# -----------------------------
# Admin Page
# -----------------------------
def admin_page():
    st.title("Admin Dashboard")
    st.subheader("Manage Users")
    users = get_all_users()

    # --- Pending Accounts first ---
    st.markdown("### Pending Accounts")
    any_pending = False
    for user in users:
        if user.username.lower() == "admin" or user.status != "pending":
            continue
        any_pending = True
        with st.container():
            st.markdown(
                f"**{user.username}** | Status: `{user.status}` | Created: {user.created_at.strftime('%Y-%m-%d %H:%M:%S')} "
            )
            c1, c2 = st.columns([1, 3])
            with c1:
                if st.button(f"Approve {user.username}", key=f"approve_{user.id}"):
                    update_user_status(user.id, "active")
                    st.success(f"{user.username} approved!")
                    st.rerun()
            with c2:
                st.caption("Approve sets status to active (no tier yet). Use section below to set a tier and activate payment window.")
    if not any_pending:
        st.info("No pending accounts.")

    st.markdown("---")
    st.markdown("### Active / Paused & Tier Control")

    # --- Manage users: tier dropdown, activate/pause, dataset/model ops, download zip ---
    for user in users:
        if user.username.lower() == "admin" or user.status == "pending":
            continue

        tier_label = {0: "None", 1: "Tier 1 (Views)", 2: "Tier 2 (Similar)", 3: "Tier 3 (Both)"}
        current_tier = user.payment_tier if user.payment_tier in (0,1,2,3) else 0

        st.markdown(
            f"**{user.username}** | Status: `{user.status}` | "
            f"Tier: `{tier_label.get(current_tier, 'None')}` | "
            f"Payment Active: `{bool(user.payment_active)}` | "
            f"Since: `{user.payment_start.strftime('%Y-%m-%d %H:%M:%S') if user.payment_start else '—'}`"
        )

        colA, colB, colC, colD = st.columns([1.2, 1.2, 1.4, 2.2])

        with colA:
            # Tier selection
            new_tier = st.selectbox(
                "Set Tier",
                options=[1, 2, 3],
                format_func=lambda x: {1: "Tier 1 (Views)", 2: "Tier 2 (Similar)", 3: "Tier 3 (Both)"}[x],
                index={1:0, 2:1, 3:2}.get(current_tier if current_tier in (1,2,3) else 1),
                key=f"tier_sel_{user.id}"
            )
            if st.button("Set Tier & Activate", key=f"set_tier_{user.id}"):
                set_tier_and_activate(user.id, new_tier)
                st.success(f"{user.username} set to {tier_label[new_tier]} and activated.")
                st.rerun()

        with colB:
            if user.status != "paused":
                if st.button("Pause User", key=f"pause_{user.id}"):
                    update_user_status(user.id, "paused")
                    st.success(f"{user.username} paused.")
                    st.rerun()
            else:
                if st.button("Reactivate User", key=f"react_{user.id}"):
                    update_user_status(user.id, "active")
                    st.success(f"{user.username} reactivated.")
                    st.rerun()

        with colC:
            # Download user folder
            if st.button("Prepare ZIP", key=f"zipbtn_{user.id}"):
                data = zip_user_folder(user.username)
                if data:
                    st.session_state[f"zip_bytes_{user.id}"] = data
                    st.success("ZIP ready below.")
                else:
                    st.warning("No user folder found to zip.")
            if f"zip_bytes_{user.id}" in st.session_state:
                st.download_button(
                    label="Download User Folder",
                    data=st.session_state[f"zip_bytes_{user.id}"],
                    file_name=f"{user.username}_bundle.zip",
                    mime="application/zip",
                    key=f"dl_{user.id}"
                )

        with colD:
            st.write("Update dataset / model")
            up_ds = st.file_uploader("Upload new dataset (CSV)", type="csv", key=f"upcsv_{user.id}")
            c1, c2 = st.columns(2)
            with c1:
                if up_ds is not None:
                    try:
                        df = pd.read_csv(up_ds)
                        
                        user_dir = f'User/{user.username}'
                        
                        # If folder already exists, remove it completely
                        if os.path.exists(user_dir):
                            shutil.rmtree(user_dir)  
                        
                        # Now save new dataset
                        admin_replace_dataset(user.username, df)
                        st.success("Dataset updated.")
                    except Exception as e:
                        st.error(f"Failed to update dataset: {e}")
            with c2:
                if st.button("Retrain Model", key=f"retrain_{user.id}"):
                    try:
                        # Assumes your training expects folder 'User/<username>' and CSV '<username>.csv'
                        mt.model_train(f'User/{user.username}', f'{user.username}.csv')
                        st.success("Model retrained.")
                    except Exception as e:
                        st.error(f"Retrain failed: {e}")

    st.markdown("---")
    if st.button("Logout (Admin)"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.is_admin = False
        st.rerun()

# -----------------------------
# Account Info Page
# -----------------------------
def account_page(user):
    # theme = st.get_option("theme.base")  # 'light' or 'dark'
    theme = st.context.theme
    theme=theme['type']
    # print(theme_info)
    # Define colors based on theme
    if theme == "dark":
        bg_card = "#5C4033"        # brownish
        bg_section = "#7B5E57"     # lighter brown for reset section
        text_color = "#f0f0f0"
        highlight_color = "#FFD700"  # golden accent
        shadow = "0 4px 12px rgba(0,0,0,0.5)"
    else:
        bg_card = "#ffffff"
        bg_section = "#e6f0ff"
        text_color = "#333333"
        highlight_color = "#1f4e8c"
        shadow = "0 4px 12px rgba(0,0,0,0.2)"

    # Global hover CSS for cards
    st.markdown(f"""
    <style>
    .hover-card {{
        transition: transform 0.3s, box-shadow 0.3s;
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 15px;
        background-color: {bg_card};
        color: {text_color};
        box-shadow: {shadow};
    }}
    .hover-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.6);
    }}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"<h1 style='text-align:center; color:{text_color};'>Account Information</h1>", unsafe_allow_html=True)

    # User Info Card
    st.markdown(f"""
    <div class="hover-card">
        <h3>Username: {user.username}</h3>
    </div>
    """, unsafe_allow_html=True)

    # Payment status + 30-day window
    if user.payment_active and user.payment_start:
        expiry = user.payment_start + timedelta(days=30)
        remaining_days = (expiry - datetime.utcnow()).days
        if remaining_days > 0:
            status_html = f"<p style='color:green;font-weight:bold;'>Payment active. {remaining_days} days remaining.</p>"
            payment_ok = True
        else:
            status_html = "<p style='color:orange;font-weight:bold;'>Payment expired! Please renew to access features.</p>"
            payment_ok = False
            update_payment(user.id, active=0)
    else:
        status_html = "<p style='color:red;font-weight:bold;'>Payment inactive! Please contact admin.</p>"
        payment_ok = False

    st.markdown(f"""
    <div class="hover-card">
        {status_html}
    </div>
    """, unsafe_allow_html=True)

    # Tier Info Cards
    tiers = [
        {"name":"Tier 1: Views Predictor", "desc":"Predict how much views a video can have in its lifetime uploaded on a certain date", "price":"$50"},
        {"name":"Tier 2: Trending & Similar", "desc":"Find the best trending movies/series for a month, get similar movies, plus Tier 1 features", "price":"$100"},
        {"name":"Tier 3: Upload Calendar", "desc":"Generate a complete list of what to upload daily monthly, plus Tier 2 features", "price":"$150"},
        {"name":"Tier 4: Smart Chatbot", "desc":"Chatbot understands your upload history and provides insights, plus Tier 3 features", "price":"$200"},
        {"name":"Tier 5: Future Premium", "desc":"All features up to Tier 4, plus more (details TBD)", "price":"$300"},
    ]

    st.markdown(f"<h2 style='text-align:center; color:{text_color};'>Available Tiers</h2>", unsafe_allow_html=True)
    for t in tiers:
        st.markdown(f"""
        <div class="hover-card">
            <h3 style='margin-bottom:5px; color:{highlight_color};'>{t['name']}</h3>
            <p>{t['desc']}</p>
            <strong>Price: {t['price']}</strong>
        </div>
        """, unsafe_allow_html=True)

    # Reset password section
    st.markdown(f"<h2 style='text-align:center; color:{text_color};'>Reset Password</h2>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="
        background-color:{bg_section};
        color:{text_color};
        padding:20px;
        border-radius:15px;
        box-shadow:{shadow};
        margin-bottom:20px;
        transition: transform 0.3s, box-shadow 0.3s;
    " onmouseover="this.style.transform='translateY(-5px)';this.style.boxShadow='0 8px 20px rgba(0,0,0,0.6)';"
       onmouseout="this.style.transform='translateY(0)';this.style.boxShadow='{shadow}';">
    """ , unsafe_allow_html=True)

    new_pass = st.text_input("New Password", type="password")
    if st.button("Reset Password"):
        if new_pass:
            reset_password(user.id, new_pass)
            st.success("Password updated!")

    st.markdown("</div>", unsafe_allow_html=True)

    # Show current tier
    tier_str = {0: "None", 1: "Tier 1", 2: "Tier 2", 3: "Tier 3", 4: "Tier 4", 5: "Tier 5"}.get(user.payment_tier or 0, "None")
    st.info(f"Your Current Tier: {tier_str}")

    return payment_ok
# -----------------------------
# User Dashboard
# -----------------------------
def secondary_page():
    if st.session_state.is_admin:
        admin_page()
        return

    user = get_user(st.session_state.username)
    st.title(f'Welcome {st.session_state.username}')

    # ---- Sidebar Style: Move to right ----
    st.markdown(
        """
        <style>
        /* Move sidebar from left to right */
        [data-testid="stSidebar"] {
            left: auto;
            right: 0;
            width: 350px; /* fixed width */
        }

        /* Shift main content so it's not hidden */
        [data-testid="stSidebar"] ~ div[data-testid="stAppViewContainer"] {
            margin-left: 0; /* remove left space */
            margin-right: 350px; /* leave space for right sidebar */
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ---- Sidebar content ----
    with st.sidebar:
        st.title("Navigation")
        page = st.radio("Go to", ["Views Predictor", "Trending & Similar", "Account Information"])

    # ---- Expiry / payment checks ----
    payment_ok = False
    # page='Views Predictor'
    if page == "Account Information":
        payment_ok = account_page(user)
    else:
        if not user.payment_active or (user.payment_start and datetime.utcnow() > user.payment_start + timedelta(days=30)):
            st.warning("Payment inactive or expired. Features disabled.")
            payment_ok = False
        else:
            payment_ok = True

    # Gate by tier
    if page == "Views Predictor":
        if not payment_ok or user.payment_tier not in (1, 3):
            st.info("Your tier does not include Views Predictor. Please contact admin.")
        else:
            st.subheader("Views Predictor")
            model_status = ut.check_model_training_status(user.username)
            if model_status == False:
                st.text('Model needs to be updated please train the model first ')
                if st.button('Train Model'):
                    mt.model_train(f'User/{user.username}', f'{user.username}.csv')
                    model_status = True
                    st.rerun()    
            else:
                movie_series_name = st.text_input('Movie/Series Name')
                date_of_release = st.text_input('Release Date (YYYY-MM-DD)').replace('/','-')
                try:
                    cache_obj = ut.cache_memory(st.session_state.username)
                    cache_obj.check_for_cache()
                    loaded_data = cache_obj.loaded_dataframe
                except:
                    loaded_data=pd.DataFrame(columns=['Title','Upload_Date','Hype_Score','Min','Max'])
                
                if st.button("Predict"):
                    try:
                        mask = (
                            loaded_data["Title"].str.lower().eq(movie_series_name.lower())
                            & loaded_data["Upload_Date"].eq(date_of_release)
                        )
                        found_data = loaded_data.loc[mask]

                        if not found_data.empty:
                            row = found_data.iloc[0]
                            results = {
                                "title": row["Title"],
                                "release date": row["Upload_Date"],
                                "hype score": row["Hype_Score"],
                                "minimum_view": row["Min"],
                                "max": row["Max"],
                            }
                        else:
                            results = mt.model_inference(
                                movie_series_name,
                                date_of_release,
                                f"User/{user.username}",
                                user.username,
                            )
                            cache_obj.dump_data(
                                results["title"],
                                results["release date"],
                                results["hype score"],
                                results["minimum_view"],
                                results["max"],
                            )

                        # ---- Render results ----
                        st.success("✅ Prediction Successful!")
                        st.markdown(
                            f"""
                            <style>
                            .movie-card {{
                                padding: 20px;
                                border-radius: 12px;
                                margin-top: 15px;
                                margin-bottom: 15px;
                                transition: transform 0.3s, box-shadow 0.3s, background-color 0.3s, color 0.3s;
                                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                            }}
                            .movie-card:hover {{
                                transform: translateY(-5px);
                                box-shadow: 0 8px 20px rgba(0,0,0,0.2);
                            }}

                            /* Light mode */
                            @media (prefers-color-scheme: light) {{
                                .movie-card {{
                                    background-color: #ffffff;
                                    color: #333;
                                }}
                                .movie-card:hover {{
                                    background-color: #f5f5f5;
                                }}
                            }}

                            /* Dark mode */
                            @media (prefers-color-scheme: dark) {{
                                .movie-card {{
                                    background-color: #5C4033;  /* brownish dark mode */
                                    color: #f5f5f5;
                                    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                                }}
                                .movie-card:hover {{
                                    background-color: #6f4e37;
                                    box-shadow: 0 8px 20px rgba(0,0,0,0.7);
                                }}
                            }}
                            </style>

                            <div class="movie-card">
                                <h3>🎬 {results['title']}</h3>
                                <p><b>📅 Release Date:</b> {results['release date']}</p>
                                <p><b>💥 Hype Score:</b> {results['hype score']}</p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        col1, col2 = st.columns(2)
                        col1.metric("Min Views", results["minimum_view"])
                        col2.metric("Max Views", results["max"])

                    except Exception as e:
                        st.error(f"Inference failed: {e}")

                if st.button("View History"):
                    
                    st.session_state.show_history = True
                    
                    st.subheader("Prediction History")
                    # Load cached data
                    cache_obj = ut.cache_memory(st.session_state.username)
                    cache_obj.check_for_cache()
                    loaded_data = cache_obj.loaded_dataframe

                    st.dataframe(loaded_data, use_container_width=True)

                    # Download CSV
                    csv = loaded_data.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="Download History as CSV",
                        data=csv,
                        file_name=f"{st.session_state.username}_history.csv",
                        mime="text/csv",
                    )
                    if st.button("Delete History"):
                        os.remove(f'User/{st.session_state.username}/{st.session_state.username}_cache.csv')                                         
                    if st.button("Close History"):
                        st.session_state.show_history = False
                        st.experimental_rerun()  # go back to main navigation page
                        st.rerun()

    elif page == "Trending & Similar":
        if not payment_ok or user.payment_tier not in (2, 3):
            st.info("Your tier does not include Trending & Similar Movies Recommender. Please contact admin.")
        else:
            st.subheader("Similar Movies Recommender")
            st.write("Feature active for your tier.")
            # Placeholder: recommender UI here

    # ---- Logout ----
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.is_admin = False
        st.rerun()

# -----------------------------
# Entry Page (Login + Signup)
# -----------------------------
def entry_page():
    # Layout preserved exactly as you requested previously
    col1, spacer, col2 = st.columns([1.5, 0.1, 2.5])
    with col1:
        # st.subheader("Login")
        login_page()
    with spacer:
        st.markdown('<div style="border-left: 3px solid #555; height: 50vh;"></div>', unsafe_allow_html=True)
    with col2:
        # st.subheader("Signup")
        signup_page()

# -----------------------------
# Main
# -----------------------------
def main():
    st.set_page_config(layout="wide")
    st.markdown(
        """
        <style>
        .sri-title {
            text-align: center;
            font-size: 2.5em;
            font-weight: bold;
            transition: color 0.3s;
        }

        /* Light mode */
        @media (prefers-color-scheme: light) {
            .sri-title {
                color: black;
            }
            .sri-divider {
                border-color: #ccc;
            }
        }

        /* Dark mode */
        @media (prefers-color-scheme: dark) {
            .sri-title {
                color: #f5f5f5;
            }
            .sri-divider {
                border-color: #666;
            }
        }
        </style>

        <h1 class="sri-title">Smart Recommendation Interface (SRI)</h1>
        <br>
        <hr class="sri-divider">
        """,
        unsafe_allow_html=True
    )


    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ''
        st.session_state.is_admin = False

    if st.session_state.logged_in:
        secondary_page()
    else:
        entry_page()

if __name__ == "__main__":
    main()
