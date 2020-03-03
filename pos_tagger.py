import nltk
#nltk.download()
import pickle
import string

import sonnet_basic
s = sonnet_basic.Sonnet_Gen()

f = open("poems/shakespeare_all_sonnets.txt", "r")
lines = f.readlines()
print(len(lines))
print(lines[-3:])

pos_file = open("poems/shakespeare_templates.txt", "a")
couplets = []
end_pos = {"NN"}

archaic = {"thou": "PRP", "thine":"NNS", "thy":"PRP$", "thee":"PRP"}
for i in range(4, len(lines) - 1, 2): #deal with punctuation?
    if len(lines[i]) < 2:
        print(lines[i])
        continue

    line1 = nltk.word_tokenize(lines[i].lower().translate(str.maketrans('', '', string.punctuation)))
    line2 = nltk.word_tokenize(lines[i+1].lower().translate(str.maketrans('', '', string.punctuation)))

    tags1 = nltk.pos_tag(line1) #doesnt work very well apparently
    tags2 = nltk.pos_tag(line2)
    print(lines[i])
    wds = lines[i].split()
    for k in range(len(wds)):
        if wds[k].upper() in s.special_words:
            tags1[k][1] = s.get_word_pos(wds[k])[0]
        if wds[k] in archaic:
            tags1[k][1] = archaic[wds[k]]



    if input("How is " + str(tags1)) == "1":
        k = [t[1] for t in tags1]
    else:
        wrong = input("Which word: " + str([(j, tags1[j], s.get_word_pos(tags1[j][0])) for j in range(len(tags1))])).split()
        k = [t[1] for t in tags1]
        for w in wrong:
            w = int(w)
            st = "which POS for " + str(tags1[w]) + str(s.get_word_pos(tags1[w][0])) + " then? "
            k[w] = input(st)

    print("ok", k)
    print(lines[i])
    write = input("write to text file?")
    if write:
        print("writing")
        pos_file.write(str(k))
    print("")
    print(lines[i+1])
    for wo in lines[i+1].split():
        if wo.upper() in s.special_words: print("warning", wo, "is a special word")


    if input(tags2) == "1":
        v = [t[1] for t in tags2]
    else:
        wrong = input("Which word: " + str([(j, tags2[j], s.get_word_pos(tags2[j][0])) for j in range(len(tags2))])).split()
        v = [t[1] for t in tags2]
        for w in wrong:
            w = int(w)
            st = "which POS for " + str(tags2[w]) + str(s.get_word_pos(tags2[w][0])) + " then? "
            v[w] = input(st)

    print("ok", v)
    print(lines[i+1])
    write = input("write to text file?")
    if write:
        print("writing")
        pos_file.write(str(k))
    print("")

    #couplets.append([k,v]) one day do this, but for now is kind of complicated or just broken
    couplets.append(k)
    couplets.append(v)


    end_pos.add(k[-1])
    end_pos.add(v[-1])


print(len(couplets))

pickle.dump(couplets, open("poems/shakespeare_tagged_verified.p", "wb"))

#pickle.dump(end_pos, open("poems/end_pos.p", "wb"))

pos_file.close()