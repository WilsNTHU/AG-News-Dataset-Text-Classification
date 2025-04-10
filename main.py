# -*- coding: utf-8 -*-
"""AG News Classification.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1nh24G8gDvFcC3CH6_b8nB4YKP_519IQT

**1. Install Required Libraries**
"""

# !pip install datasets

"""**2. Load Data**"""

import pandas as pd
df_train = pd.read_csv('train.csv')
df_test = pd.read_csv('test.csv')

print(df_train.head())
print(df_test.head())

"""**3. Preprocessing the text**"""

def combine_title_and_description(df):
  df['text'] = df[['Title', 'Description']].agg('. '.join, axis = 1)
  df = df.drop(['Title', 'Description'], axis = 1)
  return df

df_train = combine_title_and_description(df_train)
df_test = combine_title_and_description(df_test)
df_train.head()

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

nltk.download('stopwords')
stop_words = set(stopwords.words('english'))

def remove_stopwords(text):
  words = text.split()
  words = [word for word in words if word.lower() not in stop_words]
  return " ".join(words)

df_train['text'] = df_train['text'].apply(remove_stopwords)
df_test['text'] = df_test['text'].apply(remove_stopwords)

df_train['label'] = df_train['Class Index'] - 1
df_test['label'] = df_test['Class Index'] - 1

from sklearn.model_selection import train_test_split

train_texts, val_texts, train_labels, val_labels = train_test_split(
    df_train['text'].tolist(), df_train['label'].tolist(), test_size=0.2, random_state=42
)

df_train.head()

"""**4. Tokeniztion with BERT**"""

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained('bert-base-uncased')

def tokenize_function(examples):
  return tokenizer(examples['text'], padding='max_length', truncation=True, max_length=512)

train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=512)
val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=512)

"""**5. Convert Tokenized Data into PyTorch tensors**"""

import torch
from torch.utils.data import Dataset

class NewsDataset(Dataset):
  def __init__(self, encodings, labels):
      self.encodings = encodings
      self.labels = labels

  def __len__(self):  # Ensure this is properly defined
      return len(self.encodings['input_ids'])

  def __getitem__(self, idx):
      item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
      # Ensure 'input_ids' exists
      if "input_ids" not in item:
          print(f"Error: Missing 'input_ids' in dataset at index {idx}")
      item['labels'] = torch.tensor(self.labels[idx])
      return item

train_dataset = NewsDataset(train_encodings, train_labels)
test_dataset = NewsDataset(val_encodings, val_labels)
print(f"Training dataset size: {len(train_dataset)}")  # Should print a nonzero value
print(f"Validation dataset size: {len(test_dataset)}")

print(train_encodings.keys())  # Should include 'input_ids'

"""**6. Load Pretrained BERT Model**"""

from transformers import AutoModelForSequenceClassification

model = AutoModelForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=4)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

if torch.cuda.device_count() > 1:
  print(f"Using {torch.cuda.device_count()} GPUs!")
  model = torch.nn.DataParallel(model)

"""**7. Train the Model**"""

import os
os.environ["WANDB_DISABLED"] = "true"

from transformers import TrainingArguments, Trainer
from transformers import AdamW

# Define Training Arguments
training_args = TrainingArguments(
    fp16=True,
    output_dir='./results',
    evaluation_strategy="epoch",
    save_strategy="epoch",
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=3,
    logging_dir="./logs",
    warmup_steps=500,
    weight_decay=0.01,
    lr_scheduler_type="linear",
    logging_steps=10
)

# Create a Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    optimizers=(AdamW(model.parameters(), lr=5e-5), None)
)

# Train the model
trainer.train()

"""**8. Evaluate and Save the Model**"""

trainer.evaluate()

model.save_pretrained('./saved_model')
tokenizer.save_pretrained('./saved_model')

"""**9. Predict on the Test Dataset**"""

df_test.head()

test_encodings = tokenizer(df_test['text'].tolist(), truncation=True, padding=True, max_length=512)
test_dataset = NewsDataset(test_encodings, df_test['label'].tolist())

predictions = trainer.predict(test_dataset)
predicted_labels = torch.argmax(torch.tensor(predictions.predictions), axis=1)

df_test['Predicted Class'] = predicted_labels.numpy() + 1 # Convert back to 1-based index
df_test.to_csv('predictions.csv', index=False)

"""**10. Calculate the Accuracy**"""

from sklearn.metrics import accuracy_score

predicted_accuracy = accuracy_score(df_test['label'], predicted_labels.numpy())
print(f"Accuracy: {predicted_accuracy:.4f}")