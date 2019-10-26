import argparse, io

parser = argparse.ArgumentParser(description='mwe2tks')
parser.add_argument('--input', type=str, required=True)
args = parser.parse_args()
print('Removing underscores _ from {}'.format(args.input))

with io.open(args.input, 'r', encoding='utf-8') as fin, io.open("{}.tk".format(args.input), 'w+', encoding='utf-8') as fout:
    targets = fin.read().strip().split('\n')
    for summary in targets:
        output = summary.replace('_', ' ')
        fout.write("{}\n".format(output))