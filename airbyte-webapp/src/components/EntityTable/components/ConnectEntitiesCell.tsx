import React from "react";
import { FormattedMessage } from "react-intl";
import styled from "styled-components";

import { NumberBadge } from "components/ui/NumberBadge";

interface IProps {
  values: Array<{
    name: string;
    connector: string;
  }>;
  enabled?: boolean;
  entity: "source" | "destination";
}

const Content = styled.div<{ enabled?: boolean }>`
  display: flex;
  align-items: center;
  color: ${({ theme, enabled }) => (!enabled ? theme.greyColor40 : "inheret")};
`;

const Count = styled(NumberBadge)`
  margin-right: 6px;
`;

const Connector = styled.div`
  font-weight: normal;
  font-size: 12px;
  line-height: 15px;
  color: ${({ theme }) => theme.greyColor40};
`;

const ConnectEntitiesCell: React.FC<IProps> = ({ values, enabled, entity }) => {
  console.log(values.length);
  if (values.length === 1) {
    return (
      <Content enabled={enabled}>
        <Count value={1} />
        <div>
          {values[0].name}
          <Connector>{values[0].connector}</Connector>
        </div>
      </Content>
    );
  }

  if (!values.length) {
    return (
      <Content enabled={enabled}>
        <Count value={0} />
      </Content>
    );
  }

  return (
    <Content enabled={enabled}>
      <Count value={values.length} />
      <div>
        <FormattedMessage id={`tables.${entity}ConnectWithNum`} values={{ num: values.length }} />
        <Connector>{`${values[0].connector}, ${values[1].connector}${values.length > 2 ? ",..." : ""}`}</Connector>
      </div>
    </Content>
  );
};

export default ConnectEntitiesCell;
