use airoom_rust_counter::Counter;

#[test]
fn test_counter_integration_sequence() {
    let mut counter = Counter::new();
    assert_eq!(counter.value(), 0);

    // Perform a realistic sequence of counter operations
    counter.increment(10);
    counter.increment(25);
    counter.decrement(5);
    assert_eq!(counter.value(), 30);

    // Verify history tracking
    assert_eq!(counter.history(), &[0, 10, 35, 30]);

    // Reset and continue
    counter.reset();
    assert_eq!(counter.value(), 0);
    counter.increment(1);
    assert_eq!(counter.value(), 1);
    assert_eq!(counter.history(), &[0, 10, 35, 30, 0, 1]);
}
