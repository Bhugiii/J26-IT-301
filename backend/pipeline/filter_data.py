import pandas as pd

print("Loading data...")
df = pd.read_csv("sri_lanka_reviews.csv")

# List of your chosen Sri Lankan destinations
my_destinations = ["Sigiriya", "Ella", "Kataragama", "Galle", "Yala", "Kandy"]

print(f"\nFiltering for: {my_destinations}")

# Filter the dataset to only keep rows where the Location_Name matches your list
# (case=False means it ignores uppercase/lowercase differences)
filtered_df = df[df['Location_Name'].str.contains('|'.join(my_destinations), case=False, na=False)]

# Save the filtered data to a new file
filtered_df.to_csv("filtered_sri_lanka_reviews.csv", index=False)

print(f"\nSuccess! Found {len(filtered_df)} reviews for your specific destinations.")
print("Data saved to 'filtered_sri_lanka_reviews.csv'")