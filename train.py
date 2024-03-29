# -*- coding: utf-8 -*-
"""
"""

!pip install sentencepiece
!pip install -U transformers
!pip install datasets

!wget install https://raw.githubusercontent.com/monologg/KoBERT-Transformers/master/kobert_transformers/tokenization_kobert.py

from datasets import load_metric
import numpy as np
import torch.cuda
import torch
import json
import os
import csv

from transformers import(PreTrainedTokenizer,
                         T5Tokenizer as BaseT5Tokenizer,
                         BartTokenizer as BaseBartTokenizer,
                         DataCollatorForSeq2Seq,
                         Seq2SeqTrainingArguments,
                         Trainer)
from google.colab import drive
from typing import Dict, List
from transformers.models.encoder_decoder.modeling_encoder_decoder import EncoderDecoderModel
from tokenization_kobert import KoBertTokenizer

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

drive.mount('/content/gdrive/')
#/content/gdrive/MyDrive/valid_set.json

"""AI허브 데이터"""

class PairedDataset:
  def __init__(self,
               src_tokenizer:PreTrainedTokenizer, tgt_tokenizer: PreTrainedTokenizer,
               path: str):
    self.src_tokenizer = src_tokenizer
    self.trg_tokenizer = tgt_tokenizer
    with open(path,'r') as fd:
      self.data = json.load(fd)['data']
  def __getitem__(self, index:int) -> Dict[str, torch.Tensor]:
    src = self.data[index][0]['ko_original']
    trg = self.data[index][0]['en']
    embeddings = self.src_tokenizer(src, return_attention_mask=False, return_token_type_ids=False)
    embeddings['labels'] = self.trg_tokenizer(trg, return_attention_mask=False)['input_ids']

    return embeddings

  def __len__(self):
    return len(self.data)

class BartTokenizer(BaseBartTokenizer):
  def build_inputs_with_special_tokens(self, token_ids: List[int], _) -> List[int]:
    return token_ids + [self.eos_token_id]

src_tokenizer = KoBertTokenizer.from_pretrained('monologg/kobert')
trg_tokenizer = BartTokenizer.from_pretrained("facebook/bart-base")

#ai허브 데이터
datasets = PairedDataset(src_tokenizer, trg_tokenizer, '/content/gdrive/MyDrive/train__0.3.json')
eval_datasets = PairedDataset(src_tokenizer, trg_tokenizer, '/content/gdrive/MyDrive/val_0.2.json')

path = '/content/gdrive/MyDrive/dump/best_model'
file_check = os.path.isdir(path)

if file_check == True:
  model = EncoderDecoderModel.from_pretrained(path)
else:
  model = EncoderDecoderModel.from_encoder_decoder_pretrained(
      'monologg/distilkobert',
      'facebook/bart-base',
      pad_token_id = trg_tokenizer.bos_token_id
  )
model.config.decoder_start_token_id = trg_tokenizer.bos_token_id
model.cuda()

collator = DataCollatorForSeq2Seq(src_tokenizer, model)

!pip install evaluate

arguments = Seq2SeqTrainingArguments(
    output_dir='/content/dump',
    do_train = True,
    do_eval = True,
    evaluation_strategy='epoch',
    save_strategy='epoch',
    num_train_epochs=10,
    per_device_train_batch_size=40,
    per_device_eval_batch_size=40,
    warmup_ratio=0.1,
    gradient_accumulation_steps=6,
    save_total_limit=5,
    dataloader_num_workers=6,##
    fp16=True,
    load_best_model_at_end=True,
    dataloader_pin_memory=True,
    learning_rate=1e-7
)

trainer = Trainer(
    model,
    arguments,
    data_collator=collator,
    train_dataset=datasets,
    eval_dataset=eval_datasets,
)

torch.cuda.is_available()

import gc
gc.collect()
torch.cuda.empty_cache()

print("Using {} device".format(device))

trainer.train()

model.save_pretrained('/content/gdrive/MyDrive/dump/best_model')

