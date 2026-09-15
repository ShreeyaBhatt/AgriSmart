from model.infer import _crop_from_class


def test_crop_from_class_tomato():
    assert _crop_from_class("Tomato___Early_blight") == "tomato"


def test_crop_from_class_potato():
    assert _crop_from_class("Potato___Late_blight") == "potato"


def test_crop_from_class_handles_whitespace_and_case():
    assert _crop_from_class("  TOMATO___healthy  ") == "tomato"


def test_crop_mismatch_tomato_prediction_for_cotton():
    predicted_class = "Tomato___Early_blight"
    registered_crop = "cotton"

    predicted_crop = _crop_from_class(predicted_class)

    assert predicted_crop != registered_crop