dates = ["Mon", "Tue", "Wed"]

class MeetingGame:
    def __init__(self, valuations, availability, max_rounds=3):
        self.dates = dates
        self.valuations = valuations            # dict: player -> {date: value}
        self.availability = availability        # dict: player -> [date,...]
        self.max_rounds = max_rounds
        self.max_proposals = max_rounds * 2

    def is_terminal(self, history):
        # terminal if agreement or rounds exhausted
        if len(history) >= 2 and history[-1][1] == history[-2][1]:
            return True
        if len(history) >= self.max_proposals:
            return True
        return False

    def get_payoff(self, history):
        # returns (u1,u2)
        if len(history) >= 2 and history[-1] == history[-2]:
            date = history[-1][1]
            return self.valuations[1][date], self.valuations[2][date]
        return 0, 0

    def legal_actions(self, player):
        return self.availability[player]