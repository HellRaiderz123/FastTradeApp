import { Text } from 'react-native';
import { colors } from '../theme/colors';


export const PnLText = ({ value }) => {
  const isProfit = value >= 0;

  return (
    <Text
      style={{
        color: isProfit ? colors.green : colors.red,
        fontWeight: 'bold',
        fontSize: 16,
      }}
    >
      ₹{value}
    </Text>
  );
};