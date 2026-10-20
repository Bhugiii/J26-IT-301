import pandas as pd

# Load the full dataset you downloaded earlier
df = pd.read_csv("sri_lanka_reviews.csv")

# Count how many reviews exist for each location
location_counts = df['Location_Name'].value_counts()

# Print the top 60 locations that have the most reviews
print(location_counts.head(60))