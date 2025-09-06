import os
import pandas as pd

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
    

class cache_memory:
    def __init__(self,user_name):
        self.user_name=user_name
    
    def create_cache(self):
        df=pd.DataFrame(columns=['Title','Upload_Date','Hype_Score','Min','Avg','Max'])
        df.to_csv(f'User/{self.user_name}/{self.user_name}_cache.csv',index=False)

    def load_cache(self):
        df=pd.read_csv(f'User/{self.user_name}/{self.user_name}_cache.csv')
        self.loaded_dataframe=df
    
    def dump_data(self,movie_name,date,trend_score,min_view,avg_view,max_view):
        df = pd.DataFrame({
            'Title': [movie_name],
            'Upload_Date': [date],
            'Hype_Score': [trend_score],
            'Min': [min_view],
            'Avg':[avg_view],
            'Max': [max_view]
        })

        print(df)
        df.to_csv(f'User/{self.user_name}/{self.user_name}_cache.csv',mode='a',header=False,index=False)
        print('Saving Successful')
        print('#'*30)

    def check_for_cache(self):
        
        if os.path.exists(f'User/{self.user_name}/{self.user_name}_cache.csv'):
            self.load_cache()
        else: 
            self.create_cache()
    


