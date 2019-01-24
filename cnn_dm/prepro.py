import argparse
import json
import os
# data: q, cq, (dq), (pq), y, *x, *cx
# shared: x, cx, (dx), (px), word_counter, char_counter, word2vec
# no metadata
from collections import Counter

import nltk
from tqdm import tqdm

from my.utils import get_word_span, process_tokens


def bool_(arg):
    if arg == 'True':
        return True
    elif arg == 'False':
        return False
    raise Exception(arg)


def main():
    args = get_args()
    prepro(args)


def get_args():
    parser = argparse.ArgumentParser()
    home = os.path.expanduser("~")
    source_dir = os.path.join(home, "data", "cnn", 'questions')
    target_dir = "data/cnn"
    glove_dir = os.path.join(home, "data", "glove")
    parser.add_argument("--source_dir", default=source_dir)
    parser.add_argument("--target_dir", default=target_dir)
    parser.add_argument("--glove_dir", default=glove_dir)
    parser.add_argument("--glove_corpus", default='6B')
    parser.add_argument("--glove_vec_size", default=100, type=int)
    parser.add_argument("--debug", default=False, type=bool_)
    parser.add_argument("--num_sents_th", default=200, type=int)
    parser.add_argument("--sent_size_th", default=20, type=int)
    parser.add_argument("--ques_size_th", default=30, type=int)
    parser.add_argument("--width", default=9, type=int)
    # TODO : put more args here
    return parser.parse_args()


def prepro(args):
    prepro_each(args, 'train')
    prepro_each(args, 'dev')
    prepro_each(args, 'test')


def para2sents(para, width):
    """
    Turn para into double array of words (wordss)
    Where each sentence is up to 5 word neighbors of each entity
    :param para:
    :return:
    """
    """
    sents = nltk.sent_tokenize(para)
    wordss = [sent.split(" ") for sent in sents]
    return wordss
    """
    words = para.split(" ")
    sents = []
    for i, word in enumerate(words):
        if word.startswith("@"):
            start = max(i - width, 0)
            stop = min(i + width + 1, len(words))
            pre = ['-PRE-'] * max(width - i, 0)
            post = ['-POST-'] * max(width - (len(words) - i - 1), 0)
            sent = pre + words[start:stop] + post
            assert len(sent) == 2 * width + 1
            sents.append(sent)
    return sents


def get_word2vec(args, word_counter):
    glove_path = os.path.join(args.glove_dir, "glove.{}.{}d.txt".format(args.glove_corpus, args.glove_vec_size))
    sizes = {'6B': int(4e5), '42B': int(1.9e6), '840B': int(2.2e6), '2B': int(1.2e6)}
    total = sizes[args.glove_corpus]
    word2vec_dict = {}
    with open(glove_path, 'r', encoding='utf-8') as fh:
        for line in tqdm(fh, total=total):
            array = line.lstrip().rstrip().split(" ")
            word = array[0]
            vector = list(map(float, array[1:]))
            if word in word_counter:
                word2vec_dict[word] = vector
            elif word.capitalize() in word_counter:
                word2vec_dict[word.capitalize()] = vector
            elif word.lower() in word_counter:
                word2vec_dict[word.lower()] = vector
            elif word.upper() in word_counter:
                word2vec_dict[word.upper()] = vector

    print("{}/{} of word vocab have corresponding vectors in {}".format(len(word2vec_dict), len(word_counter), glove_path))
    return word2vec_dict


def prepro_each(args, mode):
    source_dir = os.path.join(args.source_dir, mode)
    word_counter = Counter()
    lower_word_counter = Counter()
    ent_counter = Counter()
    char_counter = Counter()
    max_sent_size = 0
    max_word_size = 0
    max_ques_size = 0
    max_num_sents = 0
    max_num_ents = 0

    file_names = list(os.listdir(source_dir))
    if args.debug:
        file_names = file_names[:1000]
    lens = []

    out_file_names = []
    num_skip = 0
    for file_name in tqdm(file_names, total=len(file_names)):
        if file_name.endswith(".question"):
            with open(os.path.join(source_dir, file_name), 'r') as fh:
                url = fh.readline().strip()
                _ = fh.readline()
                para = fh.readline().strip()
                _ = fh.readline()
                ques = fh.readline().strip()
                _ = fh.readline()
                answer = fh.readline().strip()
                _ = fh.readline()
                cands = list(line.strip() for line in fh)
                cand_ents = list(cand.split(":")[0] for cand in cands)
                sents = para2sents(para, args.width)
                ques_words = ques.split(" ")

                max_word_idx = max(j for sent in sents for j, word in enumerate(sent) if word == answer)
                max_sent_idx = max(i for i, sent in enumerate(sents) for word in sent if word == answer)
                max_ques_word_idx = max(i for i, word in enumerate(ques_words) if word.startswith("@"))

                # Filtering
                if max_word_idx >= args.sent_size_th or max_sent_idx >= args.num_sents_th or max_ques_word_idx >= args.ques_size_th:
                    num_skip += 1
                    continue

                max_sent_size = max(max(map(len, sents)), max_sent_size)
                max_ques_size = max(len(ques_words), max_ques_size)
                max_word_size = max(max(len(word) for sent in sents for word in sent), max_word_size)
                max_num_sents = max(len(sents), max_num_sents)
                max_num_ents = max(max_num_ents, len(cand_ents))

                for word in ques_words:
                    if word.startswith("@"):
                        ent_counter[word] += 1
                        # word_counter[word] += 1
                        # lower_word_counter[word] += 1
                    else:
                        word_counter[word] += 1
                        lower_word_counter[word.lower()] += 1
                        for c in word:
                            char_counter[c] += 1
                for sent in sents:
                    for word in sent:
                        if word.startswith("@"):
                            ent_counter[word] += 1
                            # word_counter[word] += 1
                            # lower_word_counter[word] += 1
                        else:
                            word_counter[word] += 1
                            lower_word_counter[word.lower()] += 1
                            for c in word:
                                char_counter[c] += 1

                out_file_names.append(file_name)
                lens.append(max(len(sent) for sent in sents))
    num_examples = len(out_file_names)

    assert len(out_file_names) == len(lens)
    sorted_file_names, lens = zip(*sorted(zip(out_file_names, lens), key=lambda each: each[1]))
    assert lens[-1] == max_sent_size

    word2vec_dict = get_word2vec(args, word_counter)
    lower_word2vec_dit = get_word2vec(args, lower_word_counter)

    max_num_sents = min(max_num_sents, args.num_sents_th)
    max_sent_size = min(max_sent_size, args.sent_size_th)
    max_ques_size = min(max_ques_size, args.ques_size_th)

    shared = {'word_counter': word_counter, 'ent_counter': ent_counter, 'char_counter': char_counter,
              'lower_word_counter': lower_word_counter,
              'max_num_sents': max_num_sents, 'max_sent_size': max_sent_size, 'max_word_size': max_word_size,
              'max_ques_size': max_ques_size, 'max_num_ents': max_num_ents,
              'word2vec': word2vec_dict, 'lower_word2vec': lower_word2vec_dit, 'sorted': sorted_file_names,
              'num_examples': num_examples}

    print("max num sents: {}".format(max_num_sents))
    print("max ques size: {}".format(max_ques_size))
    print("max num ents: {}".format(max_num_ents))
    print("{}/{}".format(len(sorted_file_names), len(sorted_file_names) + num_skip))

    if not os.path.exists(args.target_dir):
        os.makedirs(args.target_dir)
    shared_path = os.path.join(args.target_dir, "shared_{}.json".format(mode))
    with open(shared_path, 'w') as fh:
        json.dump(shared, fh)


if __name__ == "__main__":
    main()
