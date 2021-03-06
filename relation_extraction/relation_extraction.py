import sys
import operator

import load_data

import random
import itertools

import structures
import numpy as np
import matplotlib.pyplot as plt
import cPickle as pickle

import collections

from sklearn.linear_model import LogisticRegression
from sklearn.externals import joblib
from sklearn.model_selection import train_test_split
from sklearn.model_selection import cross_val_score
from sklearn import metrics


def create_instance_groupings(group_instances, symmetric):

    instance_to_group_dict = {}
    group_to_instance_dict = {}
    instance_dict = {}
    group = 0

    for ig in group_instances:
        start_norm = set(ig.get_sentence().get_token(ig.get_start()).get_normalized_ner().split('|'))
        end_norm = set(ig.get_sentence().get_token(ig.get_end()).get_normalized_ner().split('|'))
        instance_dict[ig] = [start_norm, end_norm]
        instance_to_group_dict[ig] = group
        group += 1

    for instance_1 in group_instances:
        max_val_start = 0
        max_val_end = 0
        for instance_2 in group_instances:

            recent_update = False

            if instance_1 == instance_2 or instance_1.get_label() != instance_2.get_label():
                continue

            if len(instance_dict[instance_1][0].intersection(instance_dict[instance_2][0])) > 0 and \
                            len(instance_dict[instance_1][1].intersection(instance_dict[instance_2][1])) > 0:
                if len(instance_dict[instance_1][0].intersection(
                        instance_dict[instance_2][0])) > max_val_start and \
                                len(instance_dict[instance_1][1].intersection(
                                    instance_dict[instance_2][1])) > max_val_end:
                    max_val_start = len(instance_dict[instance_1][0].intersection(instance_dict[instance_2][0]))
                    max_val_end = len(instance_dict[instance_1][1].intersection(instance_dict[instance_2][1]))
                    instance_to_group_dict[instance_1] = instance_to_group_dict[instance_2]
                    recent_update = True

            # check reverse direction if relation is symmetric and the forward direction wasn't incorporated
            if symmetric is True and recent_update is False:
                if len(instance_dict[instance_1][1].intersection(instance_dict[instance_2][0])) > 0 and \
                                len(instance_dict[instance_1][0].intersection(
                                    instance_dict[instance_2][1])) > 0:
                    if len(instance_dict[instance_1][1].intersection(
                            instance_dict[instance_2][0])) > max_val_start and \
                                    len(instance_dict[instance_1][0].intersection(
                                        instance_dict[instance_2][1])) > max_val_end:
                        max_val_start = len(
                            instance_dict[instance_1][1].intersection(instance_dict[instance_2][0]))
                        max_val_end = len(
                            instance_dict[instance_1][0].intersection(instance_dict[instance_2][1]))
                        instance_to_group_dict[instance_1] = instance_to_group_dict[instance_2]

    for ig in instance_to_group_dict:
        if instance_to_group_dict[ig] not in group_to_instance_dict:
            group_to_instance_dict[instance_to_group_dict[ig]] = []
        group_to_instance_dict[instance_to_group_dict[ig]].append(ig)

    return instance_to_group_dict, group_to_instance_dict, instance_dict

def k_fold_cross_validation(k,sentences_dict, distant_interactions, reverse_distant_interactions, entity_1_ids, entity_2_ids, symmetric):

    training_list = sorted(sentences_dict.iterkeys())


    #split training sentences for cross validation
    ten_fold_length = len(training_list)/k
    print(ten_fold_length)
    all_chunks = [training_list[i:i + ten_fold_length] for i in xrange(0, len(training_list), ten_fold_length)]



    total_test = np.array([])
    total_predicted_prob = np.array([])
    for i in range(len(all_chunks)):
        #print('building')
        print('Fold #: ' + str(i))
        fold_chunks = all_chunks[:]
        fold_test_abstracts = fold_chunks.pop(i)
        fold_training_abstracts = list(itertools.chain.from_iterable(fold_chunks))
        fold_training_sentences = []
        for key in fold_training_abstracts:
            fold_training_sentences = fold_training_sentences + sentences_dict[key]
        print(len(fold_training_sentences))

        fold_training_instances, fold_dep_dictionary, fold_dep_word_dictionary, fold_dep_element_dictionary, fold_between_word_dictionary = load_data.build_instances_training(
            fold_training_sentences, distant_interactions, reverse_distant_interactions, entity_1_ids, entity_2_ids, symmetric)

        #print('# of train instances: ' + str(len(fold_training_instances)))
        print(len(fold_training_instances))

        #train model
        X = []
        y = []
        for t in fold_training_instances:
            X.append(t.features)
            y.append(t.label)


        fold_train_X = np.array(X)
        fold_train_y = np.array(y)

        model = LogisticRegression()
        model.fit(fold_train_X, fold_train_y)


        for key in fold_test_abstracts:
            fold_test_sentences = sentences_dict[key]
            fold_test_instances = load_data.build_instances_testing(fold_test_sentences, fold_dep_dictionary, fold_dep_word_dictionary,fold_dep_element_dictionary,
                                                                fold_between_word_dictionary,distant_interactions,reverse_distant_interactions, entity_1_ids,entity_2_ids,symmetric)

            instance_to_group_dict, group_to_instance_dict, instance_dict = create_instance_groupings(fold_test_instances,symmetric)


            for g in group_to_instance_dict:
                group_X = []
                group_y = []
                for ti in group_to_instance_dict[g]:
                    group_X.append(ti.features)
                    group_y.append(ti.label)

                group_test_X = np.array(group_X)
                group_test_y = np.unique(group_y)

                if group_test_y.size == 1:
                    total_test = np.append(total_test, group_test_y[0])
                else:
                    continue
                    print('error')
                #total_test = np.append(total_test,group_y)

                predicted_prob = model.predict_proba(group_test_X)[:, 1]
                negation_predicted_prob = 1 - predicted_prob
                noisy_or = 1 - np.prod(negation_predicted_prob)
                total_predicted_prob = np.append(total_predicted_prob, noisy_or)

                # Generate precision recall curves

    positives = collections.Counter(total_test)[1]
    accuracy = float(positives) / total_test.size
    precision, recall, _ = metrics.precision_recall_curve(total_test, total_predicted_prob, 1)
    plt.step(recall, precision, color='b', alpha=0.2, where='post')
    plt.fill_between(recall, precision, step='post', alpha=0.2,
                         color='b')

    plt.plot((0.0, 1.0), (accuracy, accuracy))

    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.ylim([0.0, 1.05])
    plt.xlim([0.0, 1.0])
    plt.show()

def predict_sentences(model_file, abstracts, entity_1, entity_1_file, entity_1_col,
                      entity_2, entity_2_file, entity_2_col, symmetric):
    if entity_1_file.upper() != "NONE":
        entity_1_ids = load_data.load_id_list(entity_1_file, entity_1_col)
    else:
        entity_1_ids = None
    if entity_2_file.upper() != "NONE":
        entity_2_ids = load_data.load_id_list(entity_2_file, entity_2_col)
    else:
        entity_2_ids = None


    if abstracts.endswith('.pkl'):
        predict_abstract_sentences = load_data.load_abstracts_from_pickle(abstracts)
    else:
        predict_abstract_sentences = load_data.load_abstracts_from_directory(abstracts, entity_1, entity_2)

    predict_candidate_sentences = []
    for key in predict_abstract_sentences:
        predict_candidate_sentences = predict_candidate_sentences + predict_abstract_sentences[key]



    model, dep_dictionary, dep_word_dictionary, dep_element_dictionary, between_word_dictionary = joblib.load(model_file)
    predict_instances = load_data.build_instances_predict(predict_candidate_sentences, dep_dictionary,
                                                          dep_word_dictionary, dep_element_dictionary,
                                                          between_word_dictionary, entity_1_ids, entity_2_ids,
                                                          symmetric)

    X = []
    instance_sentences = set()
    for p in predict_instances:
        X.append(p.features)
        instance_sentences.add(p.get_sentence())

    X_predict = np.array(X)

    predicted_labels = model.predict(X_predict)
    print('Number of Sentences')
    print(len(instance_sentences))
    print('Number of Instances')
    print(len(predict_instances))
    return predict_instances, predicted_labels


def distant_train(model_out, abstracts, distant_file, distant_e1_col, distant_e2_col, distant_rel_col, entity_1,
                  entity_1_file, entity_1_col,
                  entity_2, entity_2_file, entity_2_col, symmetric):
    '''Method for distantly training the data'''

    #following is used to help differentiate genes that are both Human and Virus
    #get normalized ids for entity_1 optional
    if entity_1_file.upper() != "NONE":
        entity_1_ids = load_data.load_id_list(entity_1_file, entity_1_col)
    else:
        entity_1_ids = None
    #get normalized ids for entity_2
    if entity_2_file.upper() != "NONE":
        entity_2_ids = load_data.load_id_list(entity_2_file, entity_2_col)
    else:
        entity_2_ids = None

    #load the distant knowledge base
    distant_interactions, reverse_distant_interactions = load_data.load_distant_kb(distant_file, distant_e1_col,
                                                                                   distant_e2_col, distant_rel_col)
    #load the sentence data
    if abstracts.endswith('.pkl'):
        training_abstract_sentences = load_data.load_abstracts_from_pickle(abstracts)
    else:
        training_sentences = load_data.load_abstracts_from_directory(abstracts, entity_1, entity_2)
    print(len(training_abstract_sentences))

    k_fold_cross_validation(10,training_abstract_sentences,distant_interactions,reverse_distant_interactions, entity_1_ids, entity_2_ids,symmetric)




    training_sentences = []
    for key in training_abstract_sentences:
        training_sentences = training_sentences + training_abstract_sentences[key]


    training_instances, dep_dictionary, dep_word_dictionary, element_dictionary, between_word_dictionary = load_data.build_instances_training(
        training_sentences, distant_interactions, reverse_distant_interactions, entity_1_ids, entity_2_ids, symmetric)

    X = []
    y = []
    instance_sentences = set()
    for t in training_instances:
        instance_sentences.add(t.get_sentence())
        X.append(t.features)
        y.append(t.label)

    X_train = np.array(X)
    y_train = np.ravel(y)

    model = LogisticRegression()
    model.fit(X_train, y_train)
    print('Number of Sentences')
    print(len(instance_sentences))
    print('Number of Instances')
    print(len(training_instances))
    print('Number of Positive Instances')
    print(y.count(1))
    print(model.get_params)
    print('Number of dependency paths ')
    print(len(dep_dictionary))
    print('Number of dependency words')
    print(len(dep_word_dictionary))
    print('Number of between words')
    print(len(between_word_dictionary))
    print('Number of elements')
    print(len(element_dictionary))
    print('length of feature space')
    print(len(dep_dictionary) + len(dep_word_dictionary) + len(element_dictionary) + len(between_word_dictionary))
    joblib.dump((model, dep_dictionary, dep_word_dictionary, element_dictionary, between_word_dictionary), model_out)

    print("trained model")


def main():
    ''' Main method, mode determines whether program runs training, testing, or prediction'''
    mode = sys.argv[1] #what option
    if mode.upper() == "DISTANT_TRAIN":
        model_out = sys.argv[2] #location of where model should be saved after training
        sentence_file = sys.argv[3] #xml file of sentences from Stanford Parser
        distant_file = sys.argv[4] #distant supervision knowledge base to use
        distant_e1_col = int(sys.argv[5]) #entity 1 column
        distant_e2_col = int(sys.argv[6]) #entity 2 column
        distant_rel_col = int(sys.argv[7]) #relation column
        entity_1 = sys.argv[8].upper() #entity_1
        entity_1_file = sys.argv[9] #entity_1 file (i.e. human genes)
        entity_1_col = int(sys.argv[10]) #column in file of entity types
        entity_2 = sys.argv[11].upper() #entity_2
        entity_2_file = sys.argv[12] #entity_2 file location
        entity_2_col = int(sys.argv[13]) #column for entity 2
        symmetric = sys.argv[14].upper() in ['TRUE', 'Y', 'YES'] #is the relation symmetrical (i.e. binds)

        #calls training method
        distant_train(model_out, sentence_file, distant_file, distant_e1_col, distant_e2_col, distant_rel_col, entity_1,
                      entity_1_file, entity_1_col,
                      entity_2, entity_2_file, entity_2_col, symmetric)

    elif mode.upper() == "TEST":
        model_file = sys.argv[2]
        sentence_file = sys.argv[3]
        entity_1 = sys.argv[4].upper()
        entity_1_file = sys.argv[5]
        entity_1_col = int(sys.argv[6])
        entity_2 = sys.argv[7].upper()
        entity_2_file = sys.argv[8]
        entity_2_col = int(sys.argv[9])
        symmetric = sys.argv[10].upper() in ['TRUE', 'Y', 'YES']

        print('testing function not developed yet')

    elif mode.upper() == "PREDICT":
        model_file = sys.argv[2]
        sentence_file = sys.argv[3]
        entity_1 = sys.argv[4].upper()
        entity_1_file = sys.argv[5]
        entity_1_col = int(sys.argv[6])
        entity_2 = sys.argv[7].upper()
        entity_2_file = sys.argv[8]
        entity_2_col = int(sys.argv[9])
        symmetric = sys.argv[10].upper() in ['TRUE', 'Y', 'YES']

        predicted_instances, predicted_labels = predict_sentences(model_file, sentence_file, entity_1, entity_1_file,
                                                                  entity_1_col,
                                                                  entity_2, entity_2_file, entity_2_col, symmetric)

        outfile = open('/Users/kiblawi/Workspace/Data/predicted_sentences.txt', 'w')
        for i in range(len(predicted_labels)):
            pi = predicted_instances[i]
            sp = []
            ep = []
            for e in pi.get_sentence().entities:
                for l in pi.get_sentence().entities[e]:
                    if pi.start in l:
                        sp = l
                    elif pi.end in l:
                        ep = l
            outfile.write('Instance: ' + str(i) + '\n')
            outfile.write('Label: ' + str(predicted_labels[i]) + '\n')
            outfile.write(
                ' '.join('Human_gene:' + pi.get_sentence().get_token(a).get_word() for a in sp).encode(
                    'utf-8') + '\t' + 'Viral_gene:' + ' '.join(
                    pi.get_sentence().get_token(b).get_word() for b in ep).encode('utf-8') + '\n')
            outfile.write('Human_gene_index: ' + str(pi.start) + '\t' + 'Viral_gene_index: ' + str(pi.end) + '\n')
            outfile.write(pi.get_sentence().get_sentence_string().encode('utf-8') + '\n')
            outfile.write('Accuracy: \n\n')
        outfile.close()


    else:
        print("usage error")


if __name__ == "__main__":
    main()