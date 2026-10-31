

# Remove sg, pathList, A, T from the arguments for faster running.
# Best possible path algorithm is something else. Putting a reward for each
# step shall define the best possible way.
# pathList will contain the answer after the return.
GOAL_REACHED = 1
GOAL_NOT_REACHABLE = 2
GOAL_NOT_YET_REACHED = 3


class GoalSearch():

    def __init__(self, goalState, actionSpace,
                 transitionFunction, isGoalReachedFunction):
        self.sg = goalState
        self.pathList = []
        self.A = actionSpace
        self.T = transitionFunction
        self.isGR = isGoalReachedFunction

    def BruteForce(self, s):
        isgr = self.isGR(s, self.sg)
        if GOAL_NOT_YET_REACHED == isgr:
            for a in self.A:
                (sNext, c) = self.T(s, a)
                if (GOAL_REACHED == self.BruteForce(sNext)):
                    self.pathList.insert(0, ((a, c), sNext))
                    return GOAL_REACHED
            return GOAL_NOT_REACHABLE
        return isgr

    def BestSearch(self, s):
        if GOAL_NOT_REACHABLE == self.BruteForce(s):
            m = 0
            aM = None  # FIX: stays None when no deposit ends before the goal date
            for a in self.A:
                (sNext, c) = self.T(s, a)
                if (m < sNext.balance) and (
                        (self.sg.time - sNext.time).days > 0):
                    m = sNext.balance
                    aM = a
                    sNextM = sNext
                    cM = c
            if aM is not None:
                self.pathList.append(((aM, cM), sNextM))
            return GOAL_NOT_REACHABLE
        else:
            return GOAL_REACHED

    def getFinalList(self):
        return self.pathList
