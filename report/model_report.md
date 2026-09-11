# Model report — AgriSmart crop-disease classifier

- **Model:** efficientnet_b0-18c (timm EfficientNet-B0, transfer learning)
- **Eval set:** `data\plantvillage` — 630 images, 18 classes (≤35/class)
- **Split note:** internal PlantVillage subset. The hackathon's held-out field test set is scored by the organisers via `model/predict.py`.

## Metrics

| Metric | Value |
|---|---|
| Macro-F1 (primary) | **0.992** |
| Accuracy | 0.992 |
| Abstention rate | 0.000 (0/630) |

## Per-class precision / recall / F1

```
                                                    precision    recall  f1-score   support

                                Apple___Apple_scab       1.00      1.00      1.00        35
                                 Apple___Black_rot       1.00      1.00      1.00        35
                                   Apple___healthy       1.00      1.00      1.00        35
Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot       1.00      1.00      1.00        35
                       Corn_(maize)___Common_rust_       1.00      1.00      1.00        35
                            Corn_(maize)___healthy       1.00      1.00      1.00        35
                                 Grape___Black_rot       1.00      1.00      1.00        35
                                   Grape___healthy       1.00      1.00      1.00        35
                     Pepper,_bell___Bacterial_spot       0.97      1.00      0.99        35
                            Pepper,_bell___healthy       1.00      0.97      0.99        35
                             Potato___Early_blight       1.00      1.00      1.00        35
                                  Potato___healthy       1.00      1.00      1.00        35
                              Potato___Late_blight       0.95      1.00      0.97        35
                           Tomato___Bacterial_spot       1.00      1.00      1.00        35
                             Tomato___Early_blight       0.95      1.00      0.97        35
                                  Tomato___healthy       1.00      1.00      1.00        35
                              Tomato___Late_blight       1.00      0.89      0.94        35
                                Tomato___Leaf_Mold       1.00      1.00      1.00        35

                                          accuracy                           0.99       630
                                         macro avg       0.99      0.99      0.99       630
                                      weighted avg       0.99      0.99      0.99       630

```

## Confusion matrix

Rows = true, columns = predicted (last row/col = abstain).

```
     true\pred Apple___Apple_ Apple___Black_ Apple___health Corn_(maize)__ Corn_(maize)__ Corn_(maize)__ Grape___Black_ Grape___health Pepper,_bell__ Pepper,_bell__ Potato___Early Potato___healt Potato___Late_ Tomato___Bacte Tomato___Early Tomato___healt Tomato___Late_ Tomato___Leaf_    __abstain__
Apple___Apple_             35              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0
Apple___Black_              0             35              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0
Apple___health              0              0             35              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0
Corn_(maize)__              0              0              0             35              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0
Corn_(maize)__              0              0              0              0             35              0              0              0              0              0              0              0              0              0              0              0              0              0              0
Corn_(maize)__              0              0              0              0              0             35              0              0              0              0              0              0              0              0              0              0              0              0              0
Grape___Black_              0              0              0              0              0              0             35              0              0              0              0              0              0              0              0              0              0              0              0
Grape___health              0              0              0              0              0              0              0             35              0              0              0              0              0              0              0              0              0              0              0
Pepper,_bell__              0              0              0              0              0              0              0              0             35              0              0              0              0              0              0              0              0              0              0
Pepper,_bell__              0              0              0              0              0              0              0              0              1             34              0              0              0              0              0              0              0              0              0
Potato___Early              0              0              0              0              0              0              0              0              0              0             35              0              0              0              0              0              0              0              0
Potato___healt              0              0              0              0              0              0              0              0              0              0              0             35              0              0              0              0              0              0              0
Potato___Late_              0              0              0              0              0              0              0              0              0              0              0              0             35              0              0              0              0              0              0
Tomato___Bacte              0              0              0              0              0              0              0              0              0              0              0              0              0             35              0              0              0              0              0
Tomato___Early              0              0              0              0              0              0              0              0              0              0              0              0              0              0             35              0              0              0              0
Tomato___healt              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0             35              0              0              0
Tomato___Late_              0              0              0              0              0              0              0              0              0              0              0              0              2              0              2              0             31              0              0
Tomato___Leaf_              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0             35              0
   __abstain__              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0              0
```

## Limitations
- Trained on lab-condition PlantVillage images; real field photos (clutter, mixed lighting, multiple leaves) are harder — the training augmentation and test-time abstention address this but do not eliminate it.
- Subset of ~18 classes; retrain on the official kickoff label list when available.