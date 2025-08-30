import os
import pandas as pd
import model_work

class Create_User:
    def __init__(self,username,dataframe):
        self.user_name=username.replace(' ','_')
        self.dataframe=dataframe
        self.create_user_folder()
    
    def create_user_folder(self):
        os.makedirs('User',exist_ok=True)
        os.makedirs(f'User/{self.user_name}')
        self.dataframe.to_csv(f'User/{self.user_name}/{self.user_name}.csv')

def check_model_training_status(user_name):
    if 'model.pth' not in os.listdir(f'User/{user_name}'):
        return False
    else: 
        return True
    
    