
import random
import torch
import json
import numpy as np
import string
import pandas as pd


from py_files import helper

import theme_word_file
import gpt_2
import word_embeddings
from difflib import SequenceMatcher

from collections import Counter



#from transformers import BertTokenizer, BertForMaskedLM
#from transformers import RobertaTokenizer, RobertaForMaskedLM

from nltk.corpus import wordnet as wn

import poem_core



class Scenery_Gen(poem_core.Poem):
    def __init__(self, model=None, words_file="saved_objects/tagged_words.p",
                 syllables_file='saved_objects/cmudict-0.7b.txt',
                 extra_stress_file='saved_objects/edwins_extra_stresses.txt',
                 top_file='saved_objects/words/top_words.txt',
                 templates_file=('poems/jordan_templates.txt', "poems/rhetorical_templates.txt"),
                 #templates_file='poems/number_templates.txt',
                 mistakes_file=None):

        #self.templates = [("FROM scJJS scNNS PRP VBZ NN", "0_10_10_1_01_01"),
         #                 ("THAT scJJ scNN PRP VBD MIGHT RB VB", "0_10_10_1_0_10_1"),
          #                ("WHERE ALL THE scNNS OF PRP$ JJ NNS", "0_1_0_10_1_0_10_1"),
           #               ("AND THAT JJ WHICH RB VBZ NN", "0_1_01_0_10_1_01")]

        poem_core.Poem.__init__(self, words_file=words_file, templates_file=templates_file,
                                syllables_file=syllables_file, extra_stress_file=extra_stress_file, top_file=top_file, mistakes_file=mistakes_file)
        self.vocab_orig = self.pos_to_words.copy()

        if model == "bert":
            self.lang_model = BertForMaskedLM.from_pretrained('bert-base-uncased')
            self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
            self.lang_vocab = list(self.tokenizer.vocab.keys())
            self.lang_model.eval()
            self.vocab_to_num = self.tokenizer.vocab

        elif model == "roberta":
            self.lang_model = RobertaForMaskedLM.from_pretrained('roberta-base') # 'roberta-base'
            self.tokenizer = RobertaTokenizer.from_pretrained('roberta-base') # 'roberta-large'
            with open("saved_objects/roberta/vocab.json") as json_file:
                j = json.load(json_file)
            self.lang_vocab = list(j.keys())
            self.lang_model.eval()
            self.vocab_to_num = {self.lang_vocab[x]: x for x in range(len(self.lang_vocab))}


        else:
            self.lang_model = None

        #with open('poems/kaggle_poem_dataset.csv', newline='') as csvfile:
         #   self.poems = csv.DictReader(csvfile)
        self.poems = list(pd.read_csv('poems/kaggle_poem_dataset.csv')['Content'])
        self.surrounding_words = {}

        #self.gender = random.choice([["he", "him", "his", "himself"], ["she", "her", "hers", "herself"]])

        self.theme_gen = theme_word_file.Theme()

        self.word_embeddings = word_embeddings.Sim_finder()

        self.theme = ""

    #override
    def get_pos_words(self,pos, meter=None, rhyme=None, phrase=()):
        """
        Gets all the words of a given POS
        Parameters
        ----------
        pos - the POS you want
        meter - (optional) returns only words which fit the given meter, e.g. 101
        phrase (optional) - returns only words which have a phrase in the dataset. in format ([word1, word2, word3], i) where i is the index of the word to change since the length can be 2 or 3
        """
        #print("oi," , pos, meter, phrase)
        #punctuation management
        punc = [".", ",", ";", "?", ">"]
        #print("here1", pos, meter)
        #if pos[-1] in punc:
        #    p = pos[-1]
        #    if p == ">":
        #        p = random.choice(pos.split("<")[-1].strip(">").split("/"))
        #        pos = pos.split("<")[0] + p
        #    return [word + p for word in self.get_pos_words(pos[:-1], meter=meter, rhyme=rhyme)]
        #print("here", pos, meter, rhyme)
        #similar/repeated word management
        if "*VB" in pos:
            ps = []
            for po in ["VB", "VBZ", "VBG", "VBD", "VBN", "VBP"]:
                ps += self.get_pos_words(po, meter=meter, rhyme=rhyme, phrase=phrase)
            return ps
        """if pos not in self.pos_to_words and "_" in pos:
            sub_pos = pos.split("_")[0]
            word = self.weighted_choice(sub_pos, meter=meter, rhyme=rhyme)
            if not word: input("rhyme broke " + sub_pos + " " + str(meter) + " " + str(rhyme))
            #word = random.choice(poss)
            if pos.split("_")[1] in string.ascii_lowercase:
                #print("maybe breaking on", pos, word, sub_pos)
                self.pos_to_words[pos] = {word: self.pos_to_words[sub_pos][word]}
            else:
                num = pos.split("_")[1]
                if num not in self.pos_to_words:
                    #self.pos_to_words[pos] = {word:1}
                    self.pos_to_words[num] = word
                else:
                    poss = self.get_pos_words(sub_pos, meter)
                    word = self.pos_to_words[num]
                    self.pos_to_words[pos] = {w: helper.get_spacy_similarity(w, word) for w in poss}
                    return poss

            return [word]"""
        #if rhyme: return [w for w in self.get_pos_words(pos, meter=meter) if self.rhymes(w, rhyme)]
        if len(phrase) == 0 or len(phrase[0]) == 0: return super().get_pos_words(pos, meter=meter, rhyme=rhyme)
        else:
            if type(meter) == str: meter = [meter]
            ret = [word for word in self.pos_to_words[pos] if word in self.dict_meters and any(m in self.dict_meters[word] for m in meter)]
            phrases = []
            for word in ret:
                phrase[0][phrase[1]] = word
                phrases.append(" ".join(phrase[0]))
            #print(phrases, ret)
            ret = [ret[i] for i in range(len(ret)) if self.phrase_in_poem_fast(phrases[i], include_syns=True)]
            return ret

    #@override
    def last_word_dict(self, rhyme_dict):
        """
        Given the rhyme sets, extract all possible last words from the rhyme set
        dictionaries.

        Parameters
        ----------
        rhyme_dict: dictionary
            Format is   {'A': {tone1 : {similar word: [rhyming words], similar word: [rhyming words], etc.}}, {tone2:{...}}},
                        'B': {tone1 : {similar word: [rhyming words], similar word: [rhyming words], etc.}}, {tone2:{...}}}
                        etc
        Returns
        -------
        dictionary
            Format is {1: ['apple', 'orange'], 2: ['apple', orange] ... }

        """
        scheme = {1: 'A', 2: 'B', 3: 'A', 4: 'B'}
        last_word_dict = {}

        first_rhymes = []
        for i in range(1, len(scheme) + 1):
            if i in [1, 2]:  # lines with a new rhyme -> pick a random key
                last_word_dict[i] = [random.choice(
                    list(rhyme_dict[scheme[i]].keys()))]  # NB ensure it doesnt pick the same as another one
                j = 0
                while not self.suitable_last_word(last_word_dict[i][0], i - 1) or last_word_dict[i][0] in first_rhymes:
                    # or any(rhyme_dict['A'][last_word_dict[i][0]] in rhyme_dict['A'][word] for word in first_rhymes):
                    last_word_dict[i] = [random.choice(list(rhyme_dict[scheme[i]].keys()))]
                    if not any(self.templates[i - 1][1].split("_")[-1] in self.dict_meters[w] for w in
                               rhyme_dict[scheme[i]]):
                        word = last_word_dict[i][0]
                        if self.templates[i - 1][0].split()[-1] in self.get_word_pos(word) and len(
                                self.dict_meters[word][0]) == len(self.templates[i - 1][1].split("_")[-1]) and any(
                                self.suitable_last_word(r, i + 1) for r in rhyme_dict[scheme[i]][word]):
                            self.dict_meters[word].append(self.templates[i - 1][1].split("_")[-1])
                            print("cheated with ", word, " ", self.dict_meters[word],
                                  self.suitable_last_word(word, i - 1))
                    j += 1
                    if j > len(rhyme_dict[scheme[i]]) * 2: input(str(scheme[i]) + " " + str(rhyme_dict[scheme[i]]))
                first_rhymes.append(last_word_dict[i][0])

            if i in [3, 4]:  # lines with an old rhyme -> pick a random value corresponding to key of rhyming couplet
                letter = scheme[i]
                pair = last_word_dict[i - 2][0]
                last_word_dict[i] = [word for word in rhyme_dict[letter][pair] if self.suitable_last_word(word, i - 1)]
                if len(last_word_dict[i]) == 0:
                    print("fuck me", last_word_dict, i, self.templates[i])
                    print(1 / 0)
        return last_word_dict

    #@ovveride
    def suitable_last_word(self, word, line):
        pos = self.templates[line][0].split()[-1].split("sc")[-1]
        meter = self.templates[line][1].split("_")[-1]
        return pos in self.get_word_pos(word) and meter in self.dict_meters[word]


    def write_poem_flex(self, theme="love", verbose=False, random_templates=True, rhyme_lines=True, all_verbs=False, theme_lines=0, k=5, alliteration=True, theme_threshold=0.5, theme_choice="and", theme_cutoff=0.35, sum_similarity=True, theme_progression=False):
        if not self.gpt:
            if verbose: print("getting gpt")
            self.gpt = gpt_2.gpt_gen(sonnet_object=self, model="gpt2")
            #self.gpt = gpt_2.gpt_gen(sonnet_object=self, model="gpt2-large")
        self.reset_gender()

        self.theme = theme

        if theme_lines > 0: self.update_theme_words(theme=theme)
        theme_contexts = self.theme_gen.get_cases(theme) if theme_lines > 0 else [""]
        if verbose and theme_lines: print("total lines", len(theme_contexts), "e.g.", random.sample(theme_contexts, min(len(theme_contexts), theme_lines)))

        if theme and not theme_progression:
            #sub_theme = " ".join([w for w in theme.split() if len(w) > 3])
            sub_theme = theme
            if not sub_theme: sub_theme = theme

            theme_words = {}
            theme_words[sub_theme] = {}

            for pos in ['NN', 'JJ', 'RB']:
                if pos not in theme_words[sub_theme]: theme_words[sub_theme][pos] = []
                elif theme_choice == "and":
                    theme_words[sub_theme][pos] += self.get_diff_pos(sub_theme, pos, 10)
                else:
                    for t in sub_theme.split():
                        theme_words[sub_theme][pos] += self.get_diff_pos(t, pos, 10)
                if verbose: print("theme words, ", pos, ": ", len(theme_words[sub_theme][pos]), theme_words[sub_theme][pos])
            rhymes = [] #i think??
            if verbose: print("\n")
        else:
            rhymes = []
            theme_words = []
        #random.shuffle(rhymes)
        if theme and theme_progression:
            #sub_theme = " ".join([w for w in theme.split() if len(w) > 3])
            sub_theme = theme
            assert len(sub_theme.split()) == 2, sub_theme + "not good length"
            t1, t2 = sub_theme.split()
            stanza_words = {}
            stanza_themes = {}
            for stanza in range(4): #first stanza only first theme, second and third both, last only second
                stanza_theme = [t1*int(stanza <3), t2*int(stanza>0)]
                stanza_words[stanza] = self.vocab_orig.copy()
                for p in ["NN", "NNS", "ABNN"]:
                    stanza_words[stanza][p] = {word:s for (word,s) in self.pos_to_words[p].items() if self.word_embeddings.both_similarity(word, stanza_theme) > theme_cutoff}
                stanza_themes[stanza] = {}
                stanza_theme = " ".join(stanza_theme).strip()
                for pos in ['NN', 'JJ', 'RB']:
                    stanza_themes[stanza][pos] = self.get_diff_pos(stanza_theme, pos, 10)
                    if verbose: print("stanza:", stanza, ", theme words, ", pos, ": ", len(stanza_themes[stanza][pos]),
                                      stanza_themes[stanza][pos])




        else:
            for p in ["NN", "NNS", "ABNN"]:
                if verbose: print("glove cutting", [w for w in self.pos_to_words[p] if
                                                    self.word_embeddings.ft_word_similarity(w, self.theme.split()) > theme_cutoff > self.word_embeddings.gl_word_similarity(w, self.theme.split())])
                if verbose: print("\n\nfasttext cutting", [w for w in self.pos_to_words[p] if
                                                    self.word_embeddings.ft_word_similarity(w,
                                                                                            self.theme.split()) < theme_cutoff < self.word_embeddings.gl_word_similarity(
                                                        w, self.theme.split())])

                self.pos_to_words[p] = {word:s for (word,s) in self.pos_to_words[p].items() if self.word_embeddings.both_similarity(word, self.theme.split()) > theme_cutoff}
                if verbose: print("ended for", p, len(self.vocab_orig[p]), len(self.pos_to_words[p]), set(self.pos_to_words[p]))
        self.set_meter_pos_dict()


        samples = ["\n".join(random.sample(theme_contexts, theme_lines)) if theme_lines else "" for i in range(4)] #one for each stanza
        if verbose: print("samples, ", samples)
        #rhymes = []
        #theme = None

        lines = []
        used_templates = []
        choices = []
        # first three stanzas

        self.gpt_past = ""
        line_number = 0
        while line_number < 14:
            if line_number % 4 == 0:
                if verbose: print("\n\nwriting stanza", 1 + line_number/4)
                #else:
                #    if line_number > 0: print("done")
                #    if len(choices) == 0: print("\nwriting stanza", 1 + line_number/4, end=" ...")
                alliterated = not alliteration
                if theme_progression:
                    self.words_to_pos = stanza_words[int(line_number/4)]
            lines = lines[:line_number]
            used_templates = used_templates[:line_number]
            if rhyme_lines and line_number % 4 >= 2:
                r = helper.remove_punc(lines[line_number-2].split()[-1]) #last word in rhyming couplet
            elif rhyme_lines and line_number == 13:
                r = helper.remove_punc(lines[12].split()[-1])
            elif rhyme_lines and theme:
                #r = "__" + random.choice(rhymes)
                r = None #r = set(rhymes)
            else:
                r = None

            if random_templates:
                template, meter = self.get_next_template(used_templates, end=r)
                if not template:
                    if verbose: print("didnt work out for", used_templates, r)
                    continue
            else:
                template, meter = self.templates[line_number]

            #if r and len()
            alliterating = "_" not in template and not alliterated and random.random() < 0.3
            if alliterating:
                if random.random() < 0.85:
                    letters = string.ascii_lowercase
                else:
                    letters = "s"
                    #letters = string.ascii_lowercase
            else:
                letters = None


            #self.gpt_past = str(theme_lines and theme.upper() + "\n") + "\n".join(lines) #bit weird but begins with prompt if trying to be themey
            #self.gpt_past = " ".join(theme_words) + "\n" + "\n".join(lines)
            self.gpt_past = samples[0] + "\n"
            for i in range(len(lines)):
                if i % 4 == 0: self.gpt_past += samples[i//4] + "\n"
                self.gpt_past += lines[i] + "\n"
            self.reset_letter_words()
            if verbose:
                print("\nwriting line", line_number)
                print("alliterating", alliterating, letters)
                print(template, meter, r)
            t_w = theme_words[sub_theme] if not theme_progression else stanza_themes[line_number//4]
            line = self.write_line_gpt(template, meter, rhyme_word=r, flex_meter=True, verbose=verbose, all_verbs=all_verbs, alliteration=letters, theme_words=t_w, theme_threshold=theme_threshold)
            if line: line_arr = line.split()
            if line and rhyme_lines and not random_templates and line_number % 4 < 2:
                rhyme_pos = self.templates[min(line_number+2, 13)][0].split()[-1]
                #if any(self.rhymes(line.split()[-1], w) for w in self.get_pos_words(rhyme_pos)):
                if len(self.get_pos_words(rhyme_pos, rhyme=line.split()[-1])) > 0.001 * len(self.get_pos_words(rhyme_pos)):
                    if "a" in line_arr and line_arr[line_arr.index("a") + 1][0] in "aeiou": line = line.replace("a ", "an ")
                    if len(lines) % 4 == 0 or lines[-1][-1] in ".?!": line = line.capitalize()
                    if verbose: print("wrote line which rhymes with", rhyme_pos, ":", line)
                    #score = self.gpt.score_line("\n".join(random.sample(theme_contexts, min(len(theme_contexts), theme_lines))) + line)
                    score = self.gpt.score_line(line)
                    choices.append((score, line, template)) #scores with similarity to a random other line talking about it
                    if len(choices) == k:
                        best = min(choices)
                        if verbose: print("out of", len(choices), "chose", best)
                        lines.append(best[1])
                        used_templates.append(best[2])
                        line_number += 1
                        choices = []
                        if best[3]: alliterated = True
                else:
                    if verbose: print(line_number, "probably wasnt going to get a rhyme with", rhyme_pos)
                    #self.pos_to_words[template.split()[-1]][line.split()[-1]] /= 2
            elif line:
                if "a" in line_arr and line_arr[line_arr.index("a") + 1][0] in "aeiou": line = line.replace("a ", "an ")
                if len(lines) % 4 == 0 or lines[-1][-1] in ".?!": line = line.capitalize()
                line = line.replace(" i ", " I ")
                if verbose: print("wrote line", line)
                if len(lines) % 4 == 0:
                    samp = theme + "\n" + samples[len(lines)//4] + "\n" + line
                    choices.append((self.gpt.score_line(samp), line, template, alliterating))
                else:
                    curr_stanza = "\n".join(lines[len(lines) - (len(lines) % 4):])
                    #line_score = self.gpt.score_line(theme + "\n" + curr_stanza + "\n" + line)
                    line_score = self.gpt.score_line(curr_stanza + "\n" + line)
                    if sum_similarity: line_score *= sum([self.word_embeddings.ft_word_similarity(w, theme.split()) for w in line.split() if "NN" in self.get_word_pos(w) or "JJ" in self.get_word_pos(w)])
                    choices.append((line_score, line, template, alliterating))
                if len(choices) == k:
                    best = min(choices)
                    if verbose:
                        print(choices)
                        print(line_number, ":out of", len(choices), "chose", best)
                    lines.append(best[1])
                    used_templates.append(best[2])
                    line_number += 1
                    choices = []
                    if best[3]: alliterated = True
                    last = helper.remove_punc(lines[-1].split()[-1])
                    if last in rhymes: rhymes = [r for r in rhymes if r != last]
            else:
                if verbose: print("no line", template, r)
                if random.random() < (1 / len(self.templates) * 2) * (1/k):
                    if verbose: print("so resetting randomly")
                    if line_number == 13: line_number = 12
                    else: line_number -= 2

        #if not verbose and len(choices) == 0: print("done")
        ret = ("         ---" + theme.upper() + "---       , k=" + str(k) + "\n") if theme else ""
        for cand in range(len(lines)):
            ret += str(lines[cand]) + "\n"
            if ((cand + 1) % 4 == 0): ret+=("\n")
        if verbose: print(ret)

        self.pos_to_words = self.vocab_orig.copy()

        return ret


    def update_bert(self, line, meter, template, iterations, rhyme_words=[], filter_meter=True, verbose=False, choice = "min"):
        if iterations <= 0: return " ".join(line) #base case
        #TODO deal with tags like ### (which are responsible for actually cool words)
        input_ids = torch.tensor(self.tokenizer.encode(" ".join(line), add_special_tokens=False)).unsqueeze(0) #tokenizes
        tokens = [self.lang_vocab[x] for x in input_ids[0]]
        loss, outputs = self.lang_model(input_ids, masked_lm_labels=input_ids) #masks each token and gives probability for all tokens in each word. Shape num_words * vocab_size
        if verbose: print("loss = ", loss)
        softmax = torch.nn.Softmax(dim=1) #normalizes the probabilites to be between 0 and 1
        outputs = softmax(outputs[0])
        extra_token = ""
        #for word_number in range(0,len(line)-1): #ignore  last word to keep rhyme
        k = tokens.index(self.tokenizer.tokenize(line[-1])[0])  # where the last word begins

        if choice == "rand":
            word_number = out_number = random.choice(np.arange(k))

        elif choice == "min":
            probs = np.array([outputs[i][self.vocab_to_num[tokens[i]]] for i in range(k)])
            word_number = out_number = np.argmin(probs)
            while tokens[out_number].upper() in self.special_words or any(x in self.get_word_pos(tokens[out_number]) for x in ["PRP", "PRP$"]):
                if verbose: print("least likely is unchangable ", tokens, out_number, outputs[out_number][input_ids[0][out_number]])
                probs[out_number] *= 10
                word_number = out_number = np.argmin(probs)

        if len(outputs) > len(line):
            if verbose: print("before: predicting", self.lang_vocab[input_ids[0][out_number]], tokens)
            if tokens[out_number] in line:
                word_number = line.index(tokens[out_number])
                t = 1
                while "##" in self.lang_vocab[input_ids[0][out_number + t]]:
                    extra_token += self.lang_vocab[input_ids[0][out_number + 1]].split("#")[-1]
                    t += 1
                    if out_number + t >= len(input_ids[0]):
                        if verbose: print("last word chosen --> restarting", 1/0)
                        return self.update_bert(line, meter, template, iterations, rhyme_words=rhyme_words, verbose=verbose)
            else:
                sub_tokens = [self.tokenizer.tokenize(w)[0] for w in line]
                while self.lang_vocab[input_ids[0][out_number]] not in sub_tokens: out_number -= 1
                word_number = sub_tokens.index(self.lang_vocab[input_ids[0][out_number]])
                t = 1
                while "##" in self.lang_vocab[input_ids[0][out_number + t]]:
                    extra_token += self.lang_vocab[input_ids[0][word_number + t]].split("#")[-1]
                    t += 1
                    if out_number + t >= len(input_ids[0]):
                        if verbose: print("last word chosen --> restarting", 1/0)
                        return self.update_bert(line, meter, template, iterations, rhyme_words=rhyme_words, verbose=verbose)

            if verbose: print("after: ", out_number, word_number, line, " '", extra_token, "' ")

        #if verbose: print("word number ", word_number, line[word_number], template[word_number], "outnumber:", out_number)

        temp = template[word_number].split("sc")[-1]
        if len(self.get_pos_words(temp)) > 1 and temp not in ['PRP', 'PRP$']: #only change one word each time?
            filt = np.array([int( temp in self.get_word_pos(word) or temp in self.get_word_pos(word + extra_token)) for word in self.lang_vocab])
            if filter_meter and meter: filt *= np.array([int(meter[word_number] in self.get_meter(word) or meter[word_number] in self.get_meter(word + extra_token)) for word in self.lang_vocab])
            predictions = outputs[out_number].detach().numpy() * filt #filters non-words and words which dont fit meter and template

            for p in range(len(predictions)):
                if predictions[p] > 0.001 and self.lang_vocab[p] in rhyme_words:
                    print("weighting internal rhyme '", self.lang_vocab[p], "', orig: ", predictions[p], ", now: ", predictions[p]*5/sum(predictions))
                    predictions[p] *= 5
                """if predictions[p] > 0.001 and self.lang_vocab[p] in theme_words and "sc" in template[word_number]:
                    b = predictions[p]
                    input("change here and for the print")
                    predictions[p] *= theme_words[self.lang_vocab[p]]**2
                    if verbose: print("weighting thematic '", self.lang_vocab[p], "' by ", theme_words[self.lang_vocab[p]], ", now: ", predictions[p]/sum(predictions), ", was: ", b)
"""
            predictions /= sum(predictions)
            if verbose: print("predicting a ", template[word_number], meter[word_number], " for ", word_number, ". min: ", min(predictions), " max: ", max(predictions), "sum: ", sum(predictions), ", ", {self.lang_vocab[p]: predictions[p] for p in range(len(predictions)) if predictions[p] > 0})

            if iterations > 1:
                line[word_number] = np.random.choice(self.lang_vocab, p=predictions)
            else: #greedy for last iteration
                line[word_number] = self.lang_vocab[np.argmax(predictions)]

            print("word now ", line[word_number], "prob: ", predictions[self.lang_vocab.index(line[word_number])])

            if temp not in self.get_word_pos(line[word_number]):
                line[word_number] += extra_token
                if temp not in self.get_word_pos(line[word_number]): #still not valid
                    print("Extra token didnt help ", template[word_number], line[word_number], extra_token)
                    print(1/0)


            if verbose: print("line now", line)
        else:
            if verbose: print("picked ", line[word_number], "which is bad word")
            iterations += 1
        return self.update_bert(line, meter, template, iterations-1, rhyme_words=rhyme_words, verbose=verbose)

    def update_theme_words(self, word_dict={}, theme=None):
        if theme: word_dict = self.theme_gen.get_theme_words(theme)
        for pos in word_dict:
            self.pos_to_words["sc" + pos] = word_dict[pos]


    def phrase_in_poem_fast(self, words, include_syns=False):
        if type(words) == list:
            if len(words) <= 1: return True
        else:
            words = words.split()
        if len(words) > 2: return self.phrase_in_poem_fast(words[:2], include_syns=include_syns) and self.phrase_in_poem_fast(words[1:], include_syns=include_syns)
        if words[0] == words[1]: return True
        if words[0][-1] in ",.?;>" or words[1][-1] in ",.?;>": return self.phrase_in_poem_fast((words[0] + " " + words[1]).translate(str.maketrans('', '', string.punctuation)), include_syns=include_syns)
        if words[0] in self.gender: return True  # ?
        # words = " "+ words + " "

        #print("evaluating", words)

        if include_syns:
            syns = []
            for j in words:
                syns.append([l.name() for s in wn.synsets(j) for l in s.lemmas() if l.name() in self.dict_meters])
            contenders = set(words[0] + " " + w for w in syns[1])
            contenders.update([w + " " + words[1] for w in syns[0]])
            #print(words, ": " , contenders)
            return any(self.phrase_in_poem_fast(c) for c in contenders)



        if words[0] in self.surrounding_words:
            return words[1] in self.surrounding_words[words[0]]
        elif words[1] in self.surrounding_words:
            return words[0] in self.surrounding_words[words[1]]
        else:
            self.surrounding_words[words[0]] = set()
            self.surrounding_words[words[1]] = set()
            translator = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
            for poem in self.poems:
                poem = " " + poem.lower() + " "
                for word in words:
                    a = poem.find(word)
                    if a != -1 and poem[a-1] not in string.ascii_lowercase and poem[a+len(word)] not in string.ascii_lowercase:
                        #print(a, poem[a:a+len(word)])
                        p_words = poem.translate(translator).split() #remove punctuation and split
                        if word in p_words: #not ideal but eg a line which ends with a '-' confuses it
                            a = p_words.index(word)
                            if a - 1 >= 0 and a - 1 < len(p_words): self.surrounding_words[word].add(p_words[a-1])
                            if a + 1 >= 1 and a + 1 < len(p_words): self.surrounding_words[word].add(p_words[a+1])
            return self.phrase_in_poem_fast(words, include_syns=False)

    def get_backup_words(self, pos, meter, words_file="saved_objects/tagged_words.p"):
        if not self.backup_words:
            pc = poem_core.Poem()
            self.backup_words = pc.get_pos_words

        return [p for p in self.backup_words(pos) if meter in self.get_meter(p)]



    def close_adv(self, input, num=5, model_topn=50):
        if type(input) == str:
            positive = input.split() + ['happily']
        else:
            positive = input + ["happily"]
        negative = [       'happy']
        all_similar = self.word_embeddings.fasttext_model.most_similar(positive, negative, topn=model_topn)

        def score(candidate):
            ratio = SequenceMatcher(None, candidate, input).ratio()
            looks_like_adv = 1.0 if candidate.endswith('ly') else 0.0
            return ratio + looks_like_adv

        close = sorted([(word, score(word)) for word, _ in all_similar], key=lambda x: -x[1])
        return [word[0] for word in close[:num] if word[0] in self.pos_to_words["RB"]]

    def close_jj(self, input, num=5, model_topn=50):
        #positive = [input, 'dark']
        negative = [       'darkness']
        if type(input) == str:
            positive = input.split() + ['dark']
        else:
            positive = input + ["dark"]
        all_similar = self.word_embeddings.fasttext_model.most_similar(positive, negative, topn=model_topn)
        close = [word[0] for word in all_similar if word[0] in self.pos_to_words["JJ"]]

        return close

    def close_nn(self, input, num=5, model_topn=50):
        negative = ['dark']
        if type(input) == str:
            positive = input.split() + ['darkness']
        else:
            positive = input + ["darkness"]
        all_similar = self.word_embeddings.fasttext_model.most_similar(positive, negative, topn=model_topn)
        close = [word[0] for word in all_similar if word[0] in self.pos_to_words["NN"] or word[0] in self.pos_to_words["NNS"] or word[0] in self.pos_to_words["ABNN"]]

        return close

    def get_diff_pos(self, word, desired_pos, n=10):
        closest_words = [noun for noun in self.word_embeddings.get_close_words(word) if (noun in self.pos_to_words["NN"] or noun in self.pos_to_words["NNS"])]
        if desired_pos == "JJ":
            index = 0
            words = set(self.close_jj(word))
            while(len(words) < n and index < 5):
                words.update(self.close_jj(closest_words[index]))
                index += 1
            return list(words)

        if desired_pos == "RB":
            index = 0
            words = set(self.close_adv(word))
            while(len(words) < n and index < 5):
                words.update(self.close_adv(closest_words[index]))
                index += 1
            return list(words)

        if "NN" in desired_pos:
            index = 0
            words = set(self.close_nn(word))
            while(len(words) < n and index < 5):
                words.update(self.close_nn(closest_words[index]))
                index += 1
            return list(words)

        return [w for w in closest_words if desired_pos in self.get_word_pos(w)]