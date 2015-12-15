#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = 'amaury'

import os
import aiml
import marshal
import zmq
import argparse

SELF_PATH = os.path.dirname(os.path.realpath(__file__))

EAR_CHANNEL = '/alfred/hears/'
SPEECH_RECOG_CHANNEL = '/alfred/understands/'
RELOAD_TRIGGER = '/alfred/speech-recog/reload'


def parse_cli():
    parser = argparse.ArgumentParser(description='alfred-speech-recog')

    parser.add_argument('-b',
                        dest="brain_path", metavar='BRAIN_PATH', type=str,
                        help='ALICE brain file path', required=True)

    parser.add_argument('-m',
                        dest="modules_path", metavar="MODULES_PATH", type=str,
                        help='ALICE modules directory path', required=True)

    parser.add_argument('-i',
                        dest="zmq_in_addr", metavar="0MQ_INPUT_ADDR", type=str,
                        help='zero MQ address of spinal-cord''s output', required=True)

    parser.add_argument('-o',
                        dest="zmq_out_addr", metavar="0MQ_OUTPUT_ADDR", type=str,
                        help='zero MQ address of spinal-cord''s input', required=True)

    return parser.parse_args()


def main():
    args = parse_cli()
    zmq_ctx = zmq.Context()

    input_sock = zmq_ctx.socket(zmq.SUB)
    input_sock.setsockopt(zmq.SUBSCRIBE, EAR_CHANNEL)
    input_sock.connect(args.zmq_in_addr)

    publish_sock = zmq_ctx.socket(zmq.PUSH)
    publish_sock.connect(args.zmq_out_addr)

    brain = Brain(args.modules_path, args.brain_path)

    try:
        while True:
            print "zero-brain loop"

            message = receive(input_sock)

            brain_response = brain.kernel.respond(message, brain.session_name)

            if brain_response:
                if brain_response == RELOAD_TRIGGER:
                    brain.reload_modules()
                else:
                    print "zero-brain:say:" + SPEECH_RECOG_CHANNEL + brain_response
                    if brain_response.startswith('/alfred/'):
                        publish_sock.send(brain_response)
                    else:
                        publish_sock.send(SPEECH_RECOG_CHANNEL + brain_response)

    except KeyboardInterrupt:
        pass
    finally:
        brain.save_session()



def receive(bus):
    raw_message = bus.recv()

    print "zero-brain:heard:" + raw_message

    return raw_message.replace(EAR_CHANNEL, "", 1)


class Brain(object):
    def __init__(self, modules_dir, brains_dir):
        self.modules_dir = modules_dir
        self.brains_dir = brains_dir
        self.lang = 'fr-fr'
        self.kernel = aiml.Kernel()

        self.brain_file_path = os.path.join(brains_dir, 'brain.br')
        self.session_file_path = os.path.join(brains_dir, 'session.ses')

        self.brain_file = 'brain.br'
        self.session_file = 'session.ses'
        self.session_name = 'Alfred'

        self.load_brain()
        self.load_session()

    def load_brain(self):
        if os.path.isfile(self.brain_file_path):
            self.kernel.bootstrap(brainFile=self.brain_file_path)
        else:
            self.load_modules()
            self.kernel.saveBrain(self.brain_file_path)

        self.kernel.setPredicate("master", self.session_name)
        self.kernel.setBotPredicate('name', self.session_name)

    def load_session(self):
        if os.path.isfile(self.session_file_path):
            session_file = file(self.session_file_path, "rb")
            session = marshal.load(session_file)
            for pred, value in session.items():
                self.kernel.setPredicate(pred, value, self.session_name)

    def load_modules(self):
        os.path.walk(self.modules_dir, self.learn_step, self.lang)

    def learn_step(self, lang, dirname, names):
        for name in names:
            if self.lang in name and name.endswith('.aiml'):
                self.kernel.learn(os.path.join(dirname, name))

    def reload_modules(self):
        os.remove(self.brain_file_path)
        self.load_brain()
        self.save_session()

    def save_session(self):
        session_data = self.kernel.getSessionData(self.session_name)
        session_file = file(self.session_file_path, "wb")
        marshal.dump(session_data, session_file)
        session_file.close()


if __name__ == "__main__":
    main()
