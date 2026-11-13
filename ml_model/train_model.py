
from pathlib import Path
import json

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

# Project folders
BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "dataset"
MODEL_DIR = BASE_DIR / "ml_model"

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 10


def train_model():
    # Check dataset folders
    for folder in ["fake", "genuine"]:
        path = DATASET_DIR / folder

        if not path.exists() or not any(path.iterdir()):
            raise FileNotFoundError(
                f"Please add product images to: {path}"
            )

    # Load images
    train_data = keras.utils.image_dataset_from_directory(
        DATASET_DIR,
        validation_split=0.2,
        subset="training",
        seed=42,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="binary"
    )

    val_data = keras.utils.image_dataset_from_directory(
        DATASET_DIR,
        validation_split=0.2,
        subset="validation",
        seed=42,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
        label_mode="binary"
    )

    class_names = train_data.class_names
    print("Classes:", class_names)

    # Pretrained image feature extractor
    base_model = keras.applications.MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights="imagenet"
    )
    base_model.trainable = False

    inputs = keras.Input(shape=(224, 224, 3))
    x = layers.Rescaling(1.0 / 127.5, offset=-1)(inputs)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.25)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)

    model = keras.Model(inputs, outputs)

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=["accuracy"]
    )

    model.fit(
        train_data,
        validation_data=val_data,
        epochs=EPOCHS
    )

    MODEL_DIR.mkdir(exist_ok=True)
    model.save(MODEL_DIR / "model.keras")

    with open(MODEL_DIR / "classes.json", "w") as file:
        json.dump(class_names, file)

    print("Model saved successfully!")


if __name__ == "__main__":
    train_model()