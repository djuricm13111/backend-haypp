# Pseudo-code for a hybrid recommendation system

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from some_recommender_library import KNN, CosineSimilarity, TFIDF, RandomForestRecommender
from account.models import CustomUser
from product.models import Product, ProductInteraction

def load_user_data():
    return CustomUser.objects.all()

def load_product_data():
    return Product.objects.all()

def load_user_product_interactions():
    return ProductInteraction.objects.select_related('user', 'product')

def extract_user_features(users):
    user_features = []
    for user in users:
        interactions_count = ProductInteraction.objects.filter(user=user).count()
        features = {
            'user_id': user.id,
            'email': user.email,
            'full_name': user.get_full_name(),
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'activity_level': interactions_count,
        }
        user_features.append(features)
    return user_features

def extract_product_features(products):
    product_features = []
    for product in products:
        features = {
            'product_id': product.id,
            'name': product.name,
            'nicotine': product.nicotine,
            'price': product.price.amount,  # Assuming 'MoneyField' stores the amount in a 'Decimal' field
            'review': product.review,
            'category': product.category.name,
            'state': product.state,
            'manufacturer': product.manufacturer,
        }
        product_features.append(features)
    return product_features

def extract_interaction_features(interactions):
    interaction_features = []
    for interaction in interactions:
        features = {
            'user_id': interaction.user.id,
            'product_id': interaction.product.id,
            'interaction_type': interaction.interaction_type,
            'timestamp': interaction.timestamp,
            # You can extract more details from interaction.details if needed
        }
        interaction_features.append(features)
    return interaction_features


# Load your user and product data
users = load_user_data()
products = load_product_data()
interactions = load_user_product_interactions()

# Feature extraction
user_features = extract_user_features(users)
product_features = extract_product_features(products)
interaction_features = extract_interaction_features(interactions)

# Split data into training and testing sets
train_data, test_data = train_test_split(interaction_features, test_size=0.2)

# Initialize models
user_based_model = KNN(user_features)
item_based_model = CosineSimilarity(product_features)
content_based_model = TFIDF(product_features)
hybrid_model = RandomForestRecommender(user_features, product_features)

# Train models
user_based_model.fit(train_data)
item_based_model.fit(train_data)
content_based_model.fit(train_data)
hybrid_model.fit(train_data)

# Make predictions
user_based_predictions = user_based_model.predict(test_data)
item_based_predictions = item_based_model.predict(test_data)
content_based_predictions = content_based_model.predict(test_data)
hybrid_predictions = hybrid_model.predict(test_data)

# Evaluate models
user_based_error = mean_squared_error(test_data, user_based_predictions)
item_based_error = mean_squared_error(test_data, item_based_predictions)
content_based_error = mean_squared_error(test_data, content_based_predictions)
hybrid_error = mean_squared_error(test_data, hybrid_predictions)

print(f"User-Based Error: {user_based_error}")
print(f"Item-Based Error: {item_based_error}")
print(f"Content-Based Error: {content_based_error}")
print(f"Hybrid Error: {hybrid_error}")
