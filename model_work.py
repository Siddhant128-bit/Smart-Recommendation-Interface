# views.py
# Required packages:
# pip install torch torchvision scikit-learn pandas joblib

import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
import joblib
import os
import json
import get_movie_summary as gms
from datetime import datetime
from trend_score_compute import get_google_trend
import time

# =========================
# 1. Load Dataset
# =========================

def model_train(parent_directory,name_of_dataset):

    data = pd.read_csv(os.path.join(parent_directory,name_of_dataset))
    data["Video publish time"] = pd.to_datetime(data["Video publish time"])
    data["publish_day"] = data["Video publish time"].dt.day_name()

    #-----------------------------------------------------
    # Parse the embedding column (it's a string like "[0.1 0.2  ...]")
    #-----------------------------------------------------
    def parse_embedding(x):
        """
        Convert a string like "[0.1 0.2 0.3]" into a list of floats.
        If it is already a list, return it unchanged.
        """
        if isinstance(x, list):
            return x
        if isinstance(x, str):
            x = x.strip()[1:-1]  # remove [ and ]
            return [float(item) for item in x.split()]  # split by whitespace
        return x

    data["embeddings"] = data["embeddings"].apply(parse_embedding)

    #-----------------------------------------------------
    # Expand embedding -> emb_0, emb_1, ...
    #-----------------------------------------------------
    embedding_dim = len(data["embeddings"].iloc[0])
    embedding_cols = [f"emb_{i}" for i in range(embedding_dim)]
    embedding_df   = pd.DataFrame(data["embeddings"].tolist(), columns=embedding_cols)
    data = pd.concat([data, embedding_df], axis=1)

    # Keep only trend_score + weekday + embedding
    feature_cols = ["trend_score", "publish_day"] + embedding_cols
    X = data[feature_cols]
    y = (data["Views"] / 1000).values  # views (in thousands)

    TREND_WEIGHT = 1.15  # adjust until trend_score is small enough
    X["trend_score"] = X["trend_score"] * TREND_WEIGHT


    # =========================
    # 2. Preprocessing
    # =========================
    preprocessor = ColumnTransformer(
        transformers=[
            ("day", OneHotEncoder(handle_unknown="ignore"), ["publish_day"]),
            ("num", StandardScaler(), ["trend_score"] + embedding_cols)
        ]
    )

    X_processed = preprocessor.fit_transform(X)

    input_dim = X_processed.shape[1]
    print("Input Dim:", input_dim)

    # =========================
    # 3. Model
    # =========================
    class ViewPredictor(nn.Module):
        def __init__(self, input_dim):
            super().__init__()
            self.net = nn.Sequential(
                nn.Dropout(0.1),
                nn.Linear(input_dim, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Linear(64, 32),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.Dropout(0.4),

                nn.Linear(32, 1)
            )

        def forward(self, x):
            return self.net(x)

    # Train-validation split + tensor conversion
    X_train, X_val, y_train, y_val = train_test_split(X_processed, y, test_size=0.1, random_state=42)
    X_train = torch.tensor(X_train, dtype=torch.float32)
    X_val   = torch.tensor(X_val,   dtype=torch.float32)
    y_train = torch.tensor(y_train.reshape(-1,1), dtype=torch.float32)
    y_val   = torch.tensor(y_val.reshape(-1,1),   dtype=torch.float32)

    # =========================
    # 4. Training setup
    # =========================
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ViewPredictor(input_dim).to(device)


    criterion = nn.SmoothL1Loss()
    optimizer = optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-3)

    best_val = float("inf")
    best_train=float('inf')
    patience = 500
    pat_cnt  = 0

    # =========================
    # 5. Training loop
    # =========================
    epochs = 50000
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        out = model(X_train.to(device))
        loss = criterion(out, y_train.to(device))
        loss.backward()
        optimizer.step()

        model.eval()
        val_out  = model(X_val.to(device))
        val_loss = criterion(val_out, y_val.to(device)).item()

        if (epoch+1) % 25 == 0:
            print(f"Epoch {epoch+1}/{epochs} | Train: {loss.item():.4f} | Val: {val_loss:.4f}")
            train_loss= loss.item()

        if loss.item() < best_train:
            best_train=loss.item()


        if val_loss < best_val:
            best_val = val_loss
            pat_cnt = 0
            torch.save(model.state_dict(), os.path.join(parent_directory,'model.pth'))
        else:
            pat_cnt += 1
            if pat_cnt >= patience:
                print(f"Early stopping at epoch {epoch+1}")
                break

    joblib.dump(preprocessor, os.path.join(parent_directory,"preprocessor.pkl"))
    print(f'Best train loss :{best_train} best val loss: {best_val}')
    print("✅ Training complete (best model saved).")
    to_save_metadata={}
    to_save_metadata['best_train']=best_train
    to_save_metadata['best_val']=best_val
    with open(f"{parent_directory}/{name_of_dataset.replace('.csv','.json')}", "w") as outfile:
        json.dump(to_save_metadata, outfile, skipkeys=True)


def model_inference(movie_name,example_date,parent_directory,user_name):
    embedder = gms.embedder
    with open(f"{parent_directory}/{user_name}.json", "r") as f:
        to_save_metadata=json.load(f)

    best_train=to_save_metadata['best_train']
    best_val=to_save_metadata['best_val']
    # --- Load the same model definition used in training ---
    class ViewPredictor(nn.Module):
        def __init__(self, input_dim):
            super().__init__()
            self.net = nn.Sequential(
                nn.Dropout(0.1),
                nn.Linear(input_dim, 64),
                nn.BatchNorm1d(64),
                nn.ReLU(),
                nn.Dropout(0.4),
                nn.Linear(64, 32),
                nn.BatchNorm1d(32),
                nn.ReLU(),
                nn.Dropout(0.4),

                nn.Linear(32, 1)
            )

        def forward(self, x):
            return self.net(x)

        
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_factor=1-(best_train/100)
    val_factor=1-(best_val/100)
    print(train_factor,val_factor)
    def predict_views(trend_score, weekday_name, embedding_vector):
        """
        Inputs:
        trend_score (float)
        weekday_name (string)
        embedding_vector (list of floats, same size as training embeddings)
        Returns:
        views (in thousands) as a float
        """
        # load the preprocessor
        preprocessor = joblib.load(f"{parent_directory}/preprocessor.pkl")

        # build the input dataframe
        row = {
            "trend_score": trend_score,
            "publish_day": weekday_name
        }
        # add emb_0 ... emb_n
        for idx, value in enumerate(embedding_vector):
            row[f"emb_{idx}"] = value

        df_input = pd.DataFrame([row])
        X_in = preprocessor.transform(df_input)
        X_tensor = torch.tensor(X_in, dtype=torch.float32).to(device)

        # create the model with correct input-dim and load weights
        input_dim = X_in.shape[1]
        model = ViewPredictor(input_dim).to(device)
        model.load_state_dict(torch.load(f"{parent_directory}/model.pth"))
        model.eval()

        with torch.no_grad():
            pred_k = model(X_tensor).item()
        return pred_k

    train_data_df=pd.read_csv(f'{parent_directory}/{user_name}.csv')

    # -----------------------------------------------------------------------------
    # EXAMPLE USAGE
    # -----------------------------------------------------------------------------

    synopsis_flag=0

    try:
        # fetch trend score + weekday
        
        if synopsis_flag:
            embedding=gms.get_movie_synopsis_embedding(movie_name,embedder)
        else:
            embedding=gms.get_movie_summary_embedding(movie_name,embedder)
        
        # embedding=gms.get_movie_summary_embedding(movie_name,embedder)
            
        # print(f'Embeddings observed: {embedding}')

        time.sleep(45)
        print(f'target date: {example_date}')
        trend_score = int(get_google_trend(movie_name, example_date, initial_delay=60,window=30*3))
        # trend_score=45.22

        dt = datetime.strptime(example_date, "%Y-%m-%d")
        # Get weekday name

        weekday = dt.strftime("%A")
        if movie_name not in train_data_df['Video title'].tolist():
            pred_factor=val_factor
        else:
            pred_factor=train_factor



        print(f"Trend score for '{movie_name}' on {example_date}: {trend_score:.2f}, weekday: {weekday}")

        predicted = predict_views(trend_score, weekday, embedding)
        print(f"Predicted views for '{movie_name}' on {example_date}: min: {predicted*pred_factor:.2f}k max: {predicted:.2f}k")
        return {'title':movie_name,'release date': example_date,'hype score': trend_score,'minimum_view': f'{predicted*pred_factor:.2f}k','max':f'{predicted:.2f}k'}
    except Exception as e:
        print(f'Error occured as: {e}')
        return None
