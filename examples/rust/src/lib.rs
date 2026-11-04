//! Counter core library for airoom-rust-counter.

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Counter {
    value: i64,
    history: Vec<i64>,
}

impl Default for Counter {
    fn default() -> Self {
        Self::new()
    }
}

impl Counter {
    /// Create a new counter initialized at 0.
    pub fn new() -> Self {
        Self {
            value: 0,
            history: vec![0],
        }
    }

    /// Create a counter with a custom starting value.
    pub fn with_initial(initial: i64) -> Self {
        Self {
            value: initial,
            history: vec![initial],
        }
    }

    /// Return the current counter value.
    pub fn value(&self) -> i64 {
        self.value
    }

    /// Return the transition history of values.
    pub fn history(&self) -> &[i64] {
        &self.history
    }

    /// Increment the counter by the given amount.
    pub fn increment(&mut self, amount: i64) -> i64 {
        self.value += amount;
        self.history.push(self.value);
        self.value
    }

    /// Decrement the counter by the given amount.
    pub fn decrement(&mut self, amount: i64) -> i64 {
        self.value -= amount;
        self.history.push(self.value);
        self.value
    }

    /// Reset the counter to 0.
    pub fn reset(&mut self) -> i64 {
        self.value = 0;
        self.history.push(0);
        self.value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counter_defaults() {
        let counter = Counter::default();
        assert_eq!(counter.value(), 0);
        assert_eq!(counter.history(), &[0]);
    }

    #[test]
    fn test_counter_with_initial() {
        let counter = Counter::with_initial(42);
        assert_eq!(counter.value(), 42);
        assert_eq!(counter.history(), &[42]);
    }

    #[test]
    fn test_increment_and_decrement() {
        let mut counter = Counter::new();
        assert_eq!(counter.increment(5), 5);
        assert_eq!(counter.increment(3), 8);
        assert_eq!(counter.decrement(2), 6);
        assert_eq!(counter.value(), 6);
        assert_eq!(counter.history(), &[0, 5, 8, 6]);
    }

    #[test]
    fn test_reset() {
        let mut counter = Counter::new();
        counter.increment(10);
        assert_eq!(counter.value(), 10);
        assert_eq!(counter.reset(), 0);
        assert_eq!(counter.value(), 0);
        assert_eq!(counter.history(), &[0, 10, 0]);
    }
}
