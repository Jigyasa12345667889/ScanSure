
from pathlib import Path
import json

import numpy as np
import tensorflow as tf
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml_model" / "model.keras"
CLASSES_PATH = BASE_DIR / "ml_model" / "classes.json"

IMAGE_SIZE = (224, 224)


def predict_product(image_path):
    if not MODEL_PATH.exists() or not CLASSES_PATH.exists():
        raise FileNotFoundError(
            "ML model is not trained yet. Train the model first."
        )

    model = tf.keras.models.load_model(MODEL_PATH)

    with open(CLASSES_PATH, "r") as file:
        class_names = json.load(file)

    image = Image.open(image_path).convert("RGB")
    image = image.resize(IMAGE_SIZE)

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)

    prediction_score = float(
        model.predict(image_array, verbose=0)[0][0]
    )

    # Keras binary labels follow alphabetical folder order.
    predicted_index = int(prediction_score >= 0.5)
    predicted_label = class_names[predicted_index]

    confidence = (
        prediction_score
        if predicted_index == 1
        else 1 - prediction_score
    )

    return {
        "prediction": predicted_label,
        "confidence": round(confidence * 100, 2)
    }