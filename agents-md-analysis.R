library("tidyverse")
library("emmeans")
library("caret")

results <- read.csv("data/results-2026-03-11.csv") |>
  mutate(Percent.Correct = as.numeric(sub("%", "", Percent.Correct)),
         Task = factor(Task),
         Test = factor(Test))

# Overall performance
results |>
  group_by(Test) |>
  summarise(avg_score = mean(Percent.Correct)) |>
  ggplot(aes(x=Test, y=avg_score, fill=Test, group=Test)) +
  ylab("Average Percent Correct") + 
  xlab("AGENTS.md Test") +
  geom_col()

# By task
results |>
  group_by(Test, Task) |>
  summarise(avg_score = mean(Percent.Correct)) |>
  ggplot(aes(x=Test, y=avg_score, fill=Test, group=Test)) +
  ylab("Average Percent Correct") + 
  xlab("AGENTS.md Test") +
  geom_col() +
  facet_wrap(vars(Task))

# Token usage
results |>
  group_by(Test) |>
  summarise(token_usage = mean(Tokens)) |>
  ggplot(aes(x=Test, y=token_usage, fill=Test, group=Test)) +
  ylab("Average Tokens Used") + 
  xlab("AGENTS.md Test") +
  geom_col()

# By task
results |>
  group_by(Test, Task) |>
  summarise(token_usage = mean(Tokens)) |>
  ggplot(aes(x=Test, y=token_usage, fill=Test, group=Test)) +
  ylab("Average Tokens Used") + 
  xlab("AGENTS.md Test") +
  geom_col() +
  facet_wrap(vars(Task))

# Comparing token usage with performance
# Higher token usage does not correspond to better performance.
results |>
  ggplot(aes(x=Tokens, y=Percent.Correct, color=Test)) +
  geom_point() +
  geom_line() +
  scale_y_continuous(limits = c(0, 100)) + 
  facet_wrap(vars(Task))

# None of the differences are statistically significant, perhaps due to the
# very small sample size
fit <- lm(Percent.Correct ~ Test, data = results, contrasts = list(Test=contr.sum))
contrast(emmeans(fit, ~Test))

# The increased token usage by the Claude-generated file and the decreased
# token usage by no AGENTS.md do, perhaps, meet the threshold of statistical
# significance.
fit <- lm(Tokens ~ Test, data = results, contrasts = list(Test=contr.sum))
contrast(emmeans(fit, ~Test))

grouped <- results |>
  group_by(Task, Test) |>
  summarize(token_usage = mean(Tokens), avg_score = mean(Percent.Correct), .groups = "keep")
standarize_func <- preProcess(grouped, method = c("center", "scale"))
grouped <- predict(standarize_func, grouped) |>
  # Flip the sign on token_usage, so that
  # high numbers are best for both.
  mutate(score = avg_score + (-1 * token_usage))

# Overall
grouped |>
  group_by(Test) |>
  summarize(score = mean(score)) |>
  arrange(desc(score))

# FED
grouped |>
  filter(Task == "FED") |>
  group_by(Test) |>
  summarize(score = mean(score)) |>
  arrange(desc(score))

# INT
grouped |>
  filter(Task == "INT") |>
  group_by(Test) |>
  summarize(score = mean(score)) |>
  arrange(desc(score))

# BED
grouped |>
  filter(Task == "BED") |>
  group_by(Test) |>
  summarize(score = mean(score)) |>
  arrange(desc(score))