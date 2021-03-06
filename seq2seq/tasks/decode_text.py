# Copyright 2017 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Task where both the input and output sequence are plain text.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
from pydoc import locate

import os
import pickle
import copy
import codecs
import numpy as np

import tensorflow as tf
from tensorflow import gfile

from seq2seq import graph_utils
from seq2seq.tasks.inference_task import InferenceTask, unbatch_dict


def _get_prediction_length(predictions_dict):
  """Returns the length of the prediction based on the index
  of the first SEQUENCE_END token.
  """
  tokens_iter = enumerate(predictions_dict["predicted_tokens"])
  return next(((i + 1) for i, _ in tokens_iter if _ == "SEQUENCE_END"),
              len(predictions_dict["predicted_tokens"]))


def _get_unk_mapping(filename):
  """Reads a file that specifies a mapping from source to target tokens.
  The file must contain lines of the form <source>\t<target>"

  Args:
    filename: path to the mapping file

  Returns:
    A dictionary that maps from source -> target tokens.
  """
  with gfile.GFile(filename, "r") as mapping_file:
    lines = mapping_file.readlines()
    mapping = dict([_.split("\t")[0:2] for _ in lines])
    mapping = {k.strip(): v.strip() for k, v in mapping.items()}
  return mapping


def _unk_replace(source_tokens,
                 predicted_tokens,
                 attention_scores,
                 mapping=None):
  """Replaces UNK tokens with tokens from the source or a
  provided mapping based on the attention scores.

  Args:
    source_tokens: A numpy array of strings.
    predicted_tokens: A numpy array of strings.
    attention_scores: A numeric numpy array
      of shape `[prediction_length, source_length]` that contains
      the attention scores.
    mapping: If not provided, an UNK token is replaced with the
      source token that has the highest attention score. If provided
      the token is insead replaced with `mapping[chosen_source_token]`.

  Returns:
    A new `predicted_tokens` array.
  """
  result = []
  for token, scores in zip(predicted_tokens, attention_scores):
    if token == "UNK":
      max_score_index = np.argmax(scores)
      chosen_source_token = source_tokens[max_score_index]
      new_target = chosen_source_token
      if mapping is not None and chosen_source_token in mapping:
        new_target = mapping[chosen_source_token]
      result.append(new_target)
    else:
      result.append(token)
  return np.array(result)


class DecodeText(InferenceTask):
  """Defines inference for tasks where both the input and output sequences
  are plain text.

  Params:
    delimiter: Character by which tokens are delimited. Defaults to space.
    unk_replace: If true, enable unknown token replacement based on attention
      scores.
    unk_mapping: If `unk_replace` is true, this can be the path to a file
      defining a dictionary to improve UNK token replacement. Refer to the
      documentation for more details.
    dump_attention_dir: Save attention scores and plots to this directory.
    dump_attention_no_plot: If true, only save attention scores, not
      attention plots.
    dump_beams: Write beam search debugging information to this file.
  """

  def __init__(self, params):
    super(DecodeText, self).__init__(params)
    self._unk_mapping = None
    self._unk_replace_fn = None

    if self.params["unk_mapping"] is not None:
      self._unk_mapping = _get_unk_mapping(self.params["unk_mapping"])
    self._save_pred_path = self.params["save_pred_path"]
    if self.params["unk_replace"]:
      self._unk_replace_fn = functools.partial(
          _unk_replace, mapping=self._unk_mapping)

    self._postproc_fn = None
    if self.params["postproc_fn"]:
      self._postproc_fn = locate(self.params["postproc_fn"])
      if self._postproc_fn is None:
        raise ValueError("postproc_fn not found: {}".format(
            self.params["postproc_fn"]))

    self._attn_path = None
    if self.params["dump_attn_scores"] is True:
      assert self.params["attn_dir"] != ""
      assert self.params["attn_name"] != ""
      self._attn_dir = self.params["attn_dir"]
      self._attn_name = self.params["attn_name"]
      if os.path.exists(self._attn_dir) is False:
        os.makedirs(self._attn_dir)
      self._attn_path = os.path.join(self._attn_dir, self._attn_name)

  @staticmethod
  def default_params():
    params = {}
    params.update({
        "delimiter": " ",
        "postproc_fn": "",
        "unk_replace": False,
        "unk_mapping": None,
        "save_pred_path": None,
        "dump_attn_scores": False,
        "attn_dir": "",
        "attn_name": ""
    })
    return params

  def begin(self):
    self._predictions = graph_utils.get_dict_from_collection("predictions")
    self.write_cnt = 0
    self.sample_cnt = 0
    self.infer_outs = []
    self.attn_scores_list = []
    self.run_cnt = 0
    if self._save_pred_path is not None:
      self._pred_fout = codecs.open(self._save_pred_path, "w", "utf-8")
    if self._attn_path is not None:
      self._attn_fout = codecs.open(self._attn_path, "wb")

  def before_run(self, _run_context):

    if (self.run_cnt + 1) % int(1e4) == 0:
      self._pred_fout = codecs.open(self._save_pred_path, "a", "utf-8")
    fetches = {}
    fetches["predicted_tokens"] = self._predictions["predicted_tokens"]
    fetches["features.source_len"] = self._predictions["features.source_len"]
    fetches["features.source_tokens"] = self._predictions["features.source_tokens"]
    if "beam_search_output.scores" in self._predictions:
      fetches["beam_search_output.scores"] = self._predictions["beam_search_output.scores"]
    if "attention_scores" in self._predictions:
      fetches["attention_scores"] = self._predictions["attention_scores"]
    elif "beam_search_output.original_outputs.attention_scores" in self._predictions:
      fetches["beam_search_output.original_outputs.attention_scores"] = self._predictions["beam_search_output.original_outputs.attention_scores"]

    return tf.train.SessionRunArgs(fetches)

  def write_buffer_to_disk(self):
    self._pred_fout = codecs.open(self._save_pred_path, "a", "utf-8")
    if self._attn_path is not None:
      self._attn_fout = codecs.open(self._attn_path, "ab")

    for infer_out in self.infer_outs:
      self._pred_fout.write(infer_out)
      if self._attn_path is not None:
        pickle.dump( self.attn_scores_list, self._attn_fout )
        self.attn_scores_list = []
    self._pred_fout.close()
    if self._attn_path is not None:
      self._attn_fout.close()
    self.sample_cnt = 0
    self.infer_outs = []
    tf.logging.info("write times: {}".format(self.write_cnt))
    self.write_cnt += 1

  def after_run(self, _run_context, run_values):

    fetches_batch = copy.deepcopy(run_values.results)

    for fetches in unbatch_dict(fetches_batch):
      self.sample_cnt += 1
      # tf.logging.info("done samples: {}".format(self.sample_cnt))
      # Convert to unicode
      fetches["predicted_tokens"] = np.char.decode(
          fetches["predicted_tokens"].astype("S"), "utf-8")
      predicted_tokens_list = fetches["predicted_tokens"]

      fetches["features.source_tokens"] = np.char.decode(
        fetches["features.source_tokens"].astype("S"), "utf-8")
      source_tokens = fetches["features.source_tokens"]
      source_len = fetches["features.source_len"]

      source_sent = self.params["delimiter"].join(source_tokens)
      beam_search_sents = []
      beam_width = 1

      if predicted_tokens_list.ndim > 1:
        beam_width = np.shape(predicted_tokens_list)[1]

      # If we're using beam search we take the first beam
      if np.ndim(predicted_tokens_list) > 1:
        predicted_tokens = predicted_tokens_list[:, 0]

      for i in range(beam_width):
        if predicted_tokens_list.ndim > 1:
          predicted_tokens = predicted_tokens_list[:, i]
        else:
          predicted_tokens = predicted_tokens_list
        if self._unk_replace_fn is not None:
          # We slice the attention scores so that we do not
          # accidentially replace UNK with a SEQUENCE_END token
          if "beam_search_output.original_outputs.attention_scores" in fetches:
            attention_scores = fetches["beam_search_output.original_outputs.attention_scores"][:,i,:]
          else:
            attention_scores = fetches["attention_scores"]
          attention_scores = attention_scores[:, :source_len - 1]
          predicted_tokens = self._unk_replace_fn(
              source_tokens=source_tokens,
              predicted_tokens=predicted_tokens,
              attention_scores=attention_scores)

        pred_sent = self.params["delimiter"].join(predicted_tokens).split(
            "SEQUENCE_END")[0]

        # Apply postproc
        if self._postproc_fn:
          pred_sent = self._postproc_fn(pred_sent)
        pred_sent = pred_sent.strip()
        actual_source_sent = source_sent.split("SEQUENCE_END")[0].strip()
        actual_source_tokens = actual_source_sent.split(" ")
        actual_source_len = len(actual_source_tokens)
        pred_len = len(pred_sent.split(self.params["delimiter"]))

        dump_attention_scores = attention_scores[0:pred_len, 0:actual_source_len]
        self.attn_scores_list.append({
          "source_sent": actual_source_tokens,
          "pred_sent": pred_sent.split(" "),
          "attn_score": dump_attention_scores
        })
        beam_search_sents.append(pred_sent)

      pred_sents_str = "\n".join(beam_search_sents)
      if self._save_pred_path is not None:
        infer_out = source_sent + "\n" + pred_sents_str + "\n\n"
        self.infer_outs.append(infer_out)
        if self.sample_cnt % 100 == 0:
          self.write_buffer_to_disk()
      else:
        print(source_sent + "\n" + pred_sents_str + "\n\n")

  def end(self, session):

    self.write_buffer_to_disk()
    tf.logging.info("decode text end session")
    fs = []
    if self._attn_path is not None:
      fs.append(self._attn_fout)
    fs.append(self._pred_fout)
    for fout in fs:
     if fout is not None:
      if fout.closed == False:
        fout.close()
